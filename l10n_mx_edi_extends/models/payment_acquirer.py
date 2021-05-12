# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PaymentAcquirer(models.Model):
    ######################
    # Private attributes #
    ######################
    _inherit = "payment.acquirer"
    ###################
    # Default methods #
    ###################

    ######################
    # Fields declaration #
    ######################
    l10n_mx_edi_payment_method_id = fields.Many2one(string="Payment Way",
        comodel_name="l10n_mx_edi.payment.method")
    
    ##############################
    # Compute and search methods #
    ##############################

    ############################
    # Constrains and onchanges #
    ############################

    #########################
    # CRUD method overrides #
    #########################

    ##################
    # Action methods #
    ##################

    ####################
    # Business methods #
    ####################
    