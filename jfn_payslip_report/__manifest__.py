# -*- coding: utf-8 -*-
{
    "name": "JFN - Bulletin de paie (template custom)",
    "version": "17.0.1.0.0",
    "category": "Human Resources/Payroll",
    "summary": "Remplace l'impression du bulletin de paie par le template JFN + masque lignes à 0",
    "depends": ["hr_payroll"],  # Enterprise: hr_payroll est le bon socle
    "data": [
        "views/report_payslip.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
