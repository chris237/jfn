# -*- coding: utf-8 -*-
from odoo import api, models


class ReportPayslipJFN(models.AbstractModel):
    """
    Report payslip pour injecter :
    - des sections ordonnées (Basique, Allocation, Brut, Déductions, Net)
    - suppression des lignes à 0
    - dispatch des montants dans les colonnes (gain/retenue salarié, retenue patronale)

    On définit le modèle directement afin d'éviter une dépendance dure à un
    modèle de report qui peut ne pas exister selon la version/édition d'Odoo.
    """
    _name = "report.hr_payroll.report_payslip"
    _description = "JFN Payslip Report"

    # Ordre FIXE des sections (selon ton fichier de règles)
    SECTION_ORDER = [
        ("Basique", "SALAIRE DE BASE"),
        ("Allocation", "ALLOCATIONS"),
        ("Brut", "SALAIRE BRUT"),
        ("Déduction", "DEDUCTIONS"),
        ("Contribution de la société", "CONTRIBUTIONS SOCIÉTÉ"),
        ("Net", "NET"),
    ]

    # Heuristiques pour détecter "patronal" (vu tes codes & libellés)
    EMPLOYER_CODE_HINTS = {"ACC_T", "CF_P", "FNE", "ALL_F", "PV"}
    EMPLOYER_NAME_HINTS = ("patron", "patronnale", "patronal", "(patron")

    def _is_zero_line(self, line):
        # On masque toute ligne dont le total est nul (tolérance)
        return abs(line.total or 0.0) < 0.00001

    def _is_employer_line(self, line):
        rule = line.salary_rule_id
        name = (rule.name or "").lower()
        code = (rule.code or "").upper()

        if code in self.EMPLOYER_CODE_HINTS:
            return True
        if code.endswith("_P"):
            return True
        if any(h in name for h in self.EMPLOYER_NAME_HINTS):
            return True
        return False

    def _format_line_for_template(self, line):
        """
        Retourne un dict prêt pour QWeb:
        - qty/base/rate
        - gain (part salariale gain)
        - retenue_salariale
        - retenue_pat_plus / retenue_pat_minus (on remplit surtout minus comme ton pdf)
        - taux_patronal (on réutilise rate)
        """
        total = line.total or 0.0
        amount = line.amount or 0.0
        qty = line.quantity or 0.0
        rate = line.rate or 0.0

        # Colonnes
        gain = 0.0
        retenue_sal = 0.0
        retenue_pat_plus = 0.0
        retenue_pat_minus = 0.0
        taux_pat = 0.0

        if total >= 0:
            # Gains (base, allocations, etc.)
            gain = total
        else:
            # Déductions
            if self._is_employer_line(line):
                taux_pat = rate
                retenue_pat_minus = abs(total)
            else:
                retenue_sal = abs(total)

        return {
            "name": line.name,
            "code": line.code,
            "qty": qty if abs(qty) > 0.00001 else "",
            "base": amount if abs(amount) > 0.00001 else "",
            "rate": rate if abs(rate) > 0.00001 else "",
            "gain": gain if abs(gain) > 0.00001 else "",
            "retenue_sal": retenue_sal if abs(retenue_sal) > 0.00001 else "",
            "taux_pat": taux_pat if abs(taux_pat) > 0.00001 else "",
            "retenue_pat_plus": retenue_pat_plus if abs(retenue_pat_plus) > 0.00001 else "",
            "retenue_pat_minus": retenue_pat_minus if abs(retenue_pat_minus) > 0.00001 else "",
        }

    def _build_sections(self, slip):
        # Lignes visibles uniquement
        lines = slip.line_ids.filtered(lambda l: l.appears_on_payslip and not self._is_zero_line(l))

        # Group by catégorie
        by_cat = {}
        for l in lines:
            cat_name = l.category_id.name or "Autres"
            by_cat.setdefault(cat_name, []).append(l)

        sections = []
        for cat_key, title in self.SECTION_ORDER:
            cat_lines = by_cat.get(cat_key, [])
            if not cat_lines:
                continue

            # Tri stable : séquence règle puis code
            cat_lines = sorted(cat_lines, key=lambda x: (x.salary_rule_id.sequence, x.code or ""))

            sections.append({
                "key": cat_key,
                "title": title,
                "lines": [self._format_line_for_template(l) for l in cat_lines],
            })
        return sections

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["hr.payslip"].browse(docids)
        res = {
            "doc_ids": docids,
            "doc_model": "hr.payslip",
            "docs": docs,
            "data": data,
        }
        payload = []

        for slip in docs:
            payload.append({
                "slip": slip,
                "employee": slip.employee_id,
                "contract": slip.contract_id,
                "company": slip.company_id,
                "sections": self._build_sections(slip),
                # Net à payer (souvent ligne NET)
                "net_amount": slip.line_ids.filtered(lambda l: l.code == "NET")[:1].total if slip.line_ids.filtered(lambda l: l.code == "NET") else slip.net_wage,
            })

        res.update({
            "jfn_docs": payload,
        })
        return res
