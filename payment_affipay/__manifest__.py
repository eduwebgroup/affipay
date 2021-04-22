# -*- coding: utf-8 -*-
# Part of Ktrine. See LICENSE file for full copyright and licensing details.

{
    'name': 'Affipay Payment Acquirer Integration',
    'version': '12.0.0.0',
    'depends': [
        'payment'
    ],
    'external_dependencies': {},
    'author': 'Eduwebgroup',
    'website': 'https://www.eduwebgroup.com',
    'summary': 'Affipay Payment Acquirer Integration',
    'description': """
        Affipay Payment Acquirer Integration
    """,
    'category': 'Accounting/Payment Acquirers',
    'data': [
        'views/payment_acquirer_views.xml',
        'views/payment_affipay_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'qweb': [],
    'css': [],
    'images': [],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'post_init_hook': 'create_missing_journal_for_acquirers',
    'uninstall_hook': 'uninstall_hook',
}
