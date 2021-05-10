# -*- coding: utf-8 -*-
# Part of Ktrine. See LICENSE file for full copyright and licensing details.

{
    'name': 'EDI Payment Extension',
    'version': '12.0.0.0',
    'depends': [
        'l10n_mx_edi'
    ],
    'external_dependencies': {},
    'author': 'Eduwebgroup',
    'website': 'https://www.eduwebgroup.com',
    'summary': 'EDI Payment Extension',
    'description': """
        EDI Payment Extension
    """,
    'category': 'Hidden',
    'data': [
        'views/payment_acquirer_views.xml',
    ],
    'qweb': [],
    'css': [],
    'images': [],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
