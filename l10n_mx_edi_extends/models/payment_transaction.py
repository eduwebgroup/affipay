# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PaymentTransaction(models.Model):
    ######################
    # Private attributes #
    ######################
    _inherit = "payment.transaction"
    ###################
    # Default methods #
    ###################

    ######################
    # Fields declaration #
    ######################
    
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
    @api.multi
    def _prepare_account_payment_vals(self):
        self.ensure_one()
        res = super(PaymentTransaction, self)._prepare_account_payment_vals()
        res["l10n_mx_edi_payment_method_id"] = self.acquirer_id.l10n_mx_edi_payment_method_id.id if self.acquirer_id.l10n_mx_edi_payment_method_id else False,
        return res