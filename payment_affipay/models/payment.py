# -*- coding: utf-8 -*-

import base64
import datetime
from hashlib import sha256
import logging
import json

from odoo import models, fields, api, _
from odoo.http import request
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import ValidationError
from odoo.addons.payment.models.payment_acquirer import _partner_split_name

from werkzeug import urls
import requests

_logger = logging.getLogger(__name__)

def get_customer_info(partner_id, country_id=False):
    if not country_id:
        country_id = partner_id.country_id

    return {
        "firstName": "" if partner_id.is_company else _partner_split_name(partner_id.name)[0],
        "lastName": partner_id.name if partner_id.is_company else _partner_split_name(partner_id.name)[1],
        "email": partner_id.email or "",
        "address1": partner_id.street[:40] if partner_id.street else "",
        "city": partner_id.city or "",
        "country": country_id.code or "",
        "ip": request.httprequest.remote_addr or ""
    }

def sha256_hash(text: str):
    return sha256(text.encode("utf-8")).hexdigest()


def base64_encode(text: str):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


class AffipayError(Exception):
    def __init__(self, message, response: requests.Response):
        super().__init__(message)
        self.response = response


class PaymentAcquirer(models.Model):
    ######################
    # Private attributes #
    ######################
    _inherit = "payment.acquirer"
    _affipay_oauth_credentials = "blumon_pay_ecommerce_api:blumon_pay_ecommerce_api_password"

    ###################
    # Default methods #
    ###################

    ######################
    # Fields declaration #
    ######################
    provider = fields.Selection(selection_add=[("affipay", "Affipay")])
    affipay_username = fields.Char("Merchant Account ID",
        required_if_provider="affipay",
        groups="base.group_user",
        help="The username and password are provided by Affipay."
    )
    affipay_password = fields.Char("Merchant Password",
        required_if_provider="affipay",
        groups="base.group_user",
        help="The username and password are provided by Affipay."
    )

    # * This field will be changed/refreshed using _refresh_access_token() if:
    # * It is not set; or it is expired
    affipay_access_token = fields.Char(
        "Affipay Auth Access Token", default=None)
    affipay_prod_auth_url = fields.Char("Production Auth URL",
        groups="base.group_user",
        help="The Production URL to use when authenticating.")
    affipay_prod_ecommerce_url = fields.Char("Production eCommerce URL",
        groups="base.group_user",
        help="The Production URL to use when adding token or charging.")
    affipay_sandbox_auth_url = fields.Char("Sandbox Auth URL",
        groups="base.group_user",
        help="The Sandbox URL to use when authenticating.")
    affipay_sandbox_ecommerce_url = fields.Char("Sandbox eCommerce URL",
        groups="base.group_user",
        help="The Sandbox URL to use when adding token or charging.")

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
    @api.model
    def affipay_s2s_form_process(self, data):
        return self.env["payment.token"].sudo().create({
            **data,
            "name": "XXXXXXXXXXXX%s - %s" % (data.get("cc_number")[-4:], data.get("cc_holder_name")),
            "acquirer_id": int(data.get("acquirer_id")),
            "partner_id": int(data.get("partner_id"))
        })

    def affipay_s2s_form_validate(_, data):
        return all(
            [data.get(key)
                for key in
                ["cc_number",
                    "cc_brand",
                    "cc_holder_name",
                    "cc_expiry",
                    "cc_cvc"
                ]
            ])

    ####################
    # Business methods #
    ####################
    def _get_affipaypay_url(self, action):
        self.ensure_one()
        default_auth_url = "https://sandbox-tokener.blumonpay.net/oauth/token"
        default_ecommerce_url = "https://sandbox-ecommerce.blumonpay.net/ecommerce/v2/charge"
        urls = {
            "prod": {
                "oauth": self.affipay_prod_auth_url or default_auth_url,
                "ecommerce": self.affipay_prod_ecommerce_url or default_ecommerce_url,
            },
            "test": {
                "oauth": self.affipay_sandbox_auth_url or default_auth_url,
                "ecommerce": self.affipay_sandbox_ecommerce_url or default_ecommerce_url,
            }
        }
        return urls[self.environment][action]


    def _affipay_request(self, url, headers=False, data=False, params=False, json=False, method="POST"):
        self.ensure_one()
        try:
            response = requests.request(
                method, url, data=data, json=json, params=params, headers=headers)
            response.raise_for_status()
            json = response.json()
            if json.get("error"):
                raise AffipayError(json.get("error_description"), response)
            return response
        except requests.exceptions.ConnectionError as errc:
            _logger.error(errc)
            raise ValidationError("Affipay: The server is down.")
        except requests.exceptions.HTTPError as err:
            _logger.error(err)
            response = err.response
            if "application/json" in response.headers.get("Content-Type"):
                json = response.json()
                if json.get("error"):
                    raise AffipayError("Affipay: %s: %s" % (
                        json.get("error"), json.get("error_description")), response)
            raise ValidationError("An HTTP error has occurred: %s." % str(err))

    def _affipay_oauth_request(self, url, **kwargs):
        self.ensure_one()
        url = urls.url_join(self._get_affipaypay_url("oauth"), url)
        headers = kwargs.get("headers", {
            "Authorization": "Basic %s" % base64_encode(self._affipay_oauth_credentials)
        })
        try:
            response = self._affipay_request(url, headers=headers, **kwargs)
            return response.json()
        except AffipayError as e:
            res_json = e.response.json()
            err = res_json.get("error", "Error")
            err_description = res_json.get(
                "error_description", "Something is wrong with the request")
            raise ValidationError("%s: %s" % (err, err_description))

    def _affipay_ecommerce_request(self, url, eager_refresh=False, retries=2, **kwargs):
        self.ensure_one()
        if eager_refresh or not self.affipay_access_token:
            self._affipay_refresh_access_token()
        base_url = self._get_affipaypay_url("ecommerce")
        url = urls.url_join(base_url, url)
        headers = kwargs.get("headers", {
            "Authorization": "Bearer %s" % self.affipay_access_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        try:
            response = self._affipay_request(url, headers=headers, **kwargs)
            res_json = response.json()
            return res_json
        except AffipayError as e:
            res_json = e.response.json()
            if res_json.get("error") == "invalid_token":
                _logger.warn(
                    "Affipay: Invalid access token. Refreshing access token.")
                self._affipay_refresh_access_token()

                # * Retry request if received invalid token error
                if retries > 0:
                    _logger.info(
                        "Affipay: Retrying request on %s. (%i retries left)" % (url, retries))
                    retries -= 1
                    return self._affipay_ecommerce_request(url, retries=retries, **kwargs)
            err = res_json.get("error", "Error")
            err_code = err.get("httpStatusCode", 400)
            err_description = err.get(
                "description", "Something is wrong with the request")
            raise ValidationError("affipay Error: %s %s" % (err_code, err_description))

    def _affipay_refresh_access_token(self):
        self.ensure_one()
        data = self._affipay_oauth_request("/oauth/token", data={
            "grant_type": "password",
            "username": self.affipay_username,
            "password": sha256_hash(self.affipay_password),
        })
        if not data.get("access_token"):
            _logger.error(json.dumps(data))
            raise ValidationError("No access token given.")
        self.affipay_access_token = data.get("access_token")
        return self.affipay_access_token

    def _affipay_build_token_request_json(self, vals):
        partner_id = self.env["res.partner"].browse(vals.get("partner_id"))
        exp_month, exp_year = vals.get("cc_expiry").split("/")
        country_id = partner_id.country_id or self.company_id.country_id
        return {
            "pan": vals.get("cc_number", "").replace(" ", ""),
            "expMonth": exp_month.strip(),
            "expYear": "20" + exp_year.strip(),
            "holderName": vals.get("cc_holder_name"),
            "customerInformation": get_customer_info(partner_id, country_id=country_id)
        }

    def _get_feature_support(self):
        """Get advanced feature support by provider.

        Each provider should add its technical in the corresponding
        key for the following features:
            * tokenize: support saving payment data in a payment.tokenize
                        object
        """
        res = super(PaymentAcquirer, self)._get_feature_support()
        res["tokenize"].append("affipay")

        return res

class PaymentTransaction(models.Model):
    ######################
    # Private attributes #
    ######################
    _inherit = "payment.transaction"

    _affipay_supported_currencies_map = {
        "MXN": 484,
    }

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
    def affipay_s2s_do_transaction(self, **kwargs):
        self.ensure_one()
        if self.currency_id.name not in self._affipay_supported_currencies_map.keys():
            raise ValidationError(
                "Currency %s not supported." % self.currency_id.name)
        payment_token = self.payment_token_id
        acquirer = self.acquirer_id
        try:
            ecommerce_data = acquirer._affipay_ecommerce_request("/ecommerce/v2/charge", json={
                "amount": float(self.amount) if acquirer.environment == "prod" else min(float(self.amount), 20.0),
                "currency": self._affipay_supported_currencies_map[self.currency_id.name],
                "noPresentCardData": {
                    "cardToken": payment_token.acquirer_ref,
                }
            })
        except AffipayError as e:
            ecommerce_data = e.response.json()
        return self._affipay_s2s_validate_tree(ecommerce_data)

    ####################
    # Business methods #
    ####################
    def _affipay_s2s_validate_tree(self, tree, call_type="charge"):
        self.ensure_one()
        if self.state not in ["draft", "pending"]:
            _logger.info(
                "Affipay: trying to validate an already validated transaction (ref %s)", self.reference)
            return True
        if tree.get("status") and tree.get("dataResponse", {}).get("description") == "APROBADA":
            self.write({
                "date": datetime.date.today().strftime(DEFAULT_SERVER_DATE_FORMAT),
                "acquirer_reference": tree.get("id")
            })
            if call_type == "charge":
                # E-Commerce charge success
                if self.partner_id and not self.payment_token_id and \
                        (self.type == "form_save" or self.acquirer_id.save_token == "always"):
                    self.payment_token_id = self.acquirer_id.affipay_s2s_form_process(
                        dict(request.params)).id
                if self.payment_token_id:
                    self.payment_token_id.verified = True
                self._set_transaction_done()
                self.execute_callback()
            return True
        error = tree.get("error", {})
        error_code = error.get("code", "ERR")
        error_description = error.get(
            "description", "Affipay API gave an error response.")
        _logger.error(json.dumps(tree))
        self._set_transaction_error(
            "Affipay API Error: %s - %s" % (error_code, error_description))
        return False

class PaymentToken(models.Model):
    ######################
    # Private attributes #
    ######################
    _inherit = "payment.token"

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
    @api.model
    def affipay_create(self, vals):
        if vals.get("cc_number"):
            payment_acquirer = self.env["payment.acquirer"].browse(vals.get("acquirer_id"))
            response = payment_acquirer._affipay_ecommerce_request("/cardToken/add",
                json=payment_acquirer._affipay_build_token_request_json(vals))
            if response.get("status") and response.get("dataResponse"):
                vals.update({
                    "acquirer_ref": response.get("dataResponse")["id"],
                    "name": vals.get("name"),
                })
                return vals
            else:
                raise ValidationError("Error: %s" % response.get(
                    "error", {}).get("description", ""))
        return {}

    ##################
    # Action methods #
    ##################

    ####################
    # Business methods #
    ####################