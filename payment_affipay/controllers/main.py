# -*- coding: utf-8 -*-
import logging

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class AffipayController(http.Controller):
    @http.route(["/payment/affipay/s2s/create_json_3ds"], type="json", auth="public", csrf=False)
    def affipay_s2s_create_json_3ds(self, verify_validity=False, **kwargs):
        if not kwargs.get('partner_id'):
            kwargs.update({
                "partner_id": request.env.user.partner_id.id
            })
        try:
            token = (
                request.env["payment.acquirer"]
                .browse(int(kwargs.get("acquirer_id")))
                .s2s_process(kwargs)
            )
            if not token:
                return {
                    "result": False
                }
            return {
                "short_name": token.short_name,
                "3d_secure": False,
                "verified": False,
                "result": True,
                "id": token.id,
            }
        except Exception as e:
            return {
                "result": False,
                "error": str(e),
            }
