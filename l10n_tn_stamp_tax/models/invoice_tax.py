# -*- coding: utf-8 -*-

from odoo import models, fields, api, http
import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax.template"

    is_stamp = fields.Boolean("Is Stamp Tax")
    fodec = fields.Boolean("FODEC")


class AccountTax(models.Model):
    _inherit = "account.tax"

    is_stamp = fields.Boolean("Is Stamp Tax")
    fodec = fields.Boolean("FODEC")


class InvoiceStampTax(models.Model):
    _inherit = 'account.move'

    stamp_tax = fields.Many2one('account.tax',string="Stamp Tax", domain=[('is_stamp', '=', True)])
    fodec = fields.Many2one('account.tax',string="FODEC", domain=[('fodec', '=', True)])

    @api.onchange('stamp_tax')
    def _onchange_stam_tax(self):
        self.update_tax()
        self._recompute_stamp_tax_lines()
        self._recompute_payment_terms_lines()


    def update_tax(self):
        for rec in self:
            stamp_lines = self.line_ids.filtered(
                lambda line: line.name and line.name.find('Droit de Timbre') == 0)
            terms_lines = self.line_ids.filtered(
                lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
            other_lines = self.line_ids.filtered(
                lambda line: line.account_id.user_type_id.type not in ('receivable', 'payable'))
            if stamp_lines and rec.stamp_tax:
                tax = rec.stamp_tax.compute_all(rec.amount_total, currency=rec.currency_id, quantity=1, product=None, partner=rec.partner_id)['taxes'][0]
                amount = tax['amount']
                if (rec.move_type == "out_invoice"
                             or rec.move_type == "out_refund"):
                    if rec.move_type == "out_invoice":
                        stamp_lines.update({
                            'debit': amount < 0.0 and -amount or 0.0,
                            'credit': amount > 0.0 and amount or 0.0,
                        })
                    else:
                        stamp_lines.update({
                            'debit': amount > 0.0 and amount or 0.0,
                            'credit': amount < 0.0 and -amount or 0.0,
                        })
                if (rec.move_type == "in_invoice"
                             or rec.move_type == "in_refund"):
                    if rec.move_type == "in_invoice":
                        stamp_lines.update({
                            'debit': amount > 0.0 and amount or 0.0,
                            'credit': amount < 0.0 and -amount or 0.0,
                        })
                    else:
                        stamp_lines.update({
                            'debit': amount < 0.0 and -amount or 0.0,
                            'credit': amount > 0.0 and amount or 0.0,
                        })
                total_balance = sum(other_lines.mapped('balance'))
                total_amount_currency = sum(other_lines.mapped('amount_currency'))
                terms_lines.update({
                    'amount_currency': -total_amount_currency,
                    'debit': total_balance < 0.0 and -total_balance or 0.0,
                    'credit': total_balance > 0.0 and total_balance or 0.0,
                })

    def _recompute_stamp_tax_lines(self):
        for rec in self:
            type_list = ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']
            if rec.stamp_tax and rec.move_type in type_list:
                tax = rec.stamp_tax.compute_all(rec.amount_total, currency=rec.currency_id, quantity=1, product=None,
                                                partner=rec.partner_id)['taxes'][0]
                amount = tax['amount']
                if rec.is_invoice(include_receipts=True):
                    in_draft_mode = self != self._origin
                    name = "Droit de Timbre"                    
                    terms_lines = self.line_ids.filtered(
                        lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
                    stamp_lines = self.line_ids.filtered(
                        lambda line: line.name and line.name.find('Droit de Timbre') == 0)
                    if stamp_lines:

                        if(self.move_type == "out_invoice" or self.move_type == "out_refund"):
                            stamp_lines.update({
                                'name': name,
                                'debit': amount < 0.0 and -amount or 0.0,
                                'credit': amount > 0.0 and amount or 0.0,
                            })
                        if (self.move_type == "in_invoice" or self.move_type == "in_refund"):
                            stamp_lines.update({
                                'name': name,
                                'debit': amount > 0.0 and amount or 0.0,
                                'credit': amount < 0.0 and -amount or 0.0,
                            })
                    else:
                        new_tax_line = self.env['account.move.line']
                        create_method = in_draft_mode and \
                                        self.env['account.move.line'].new or \
                                        self.env['account.move.line'].create

                        if  (self.move_type == "out_invoice"
                                     or self.move_type == "out_refund"):
                            dict = {
                                'move_name': self.name,
                                'name': name,
                                'price_unit': amount,
                                'quantity': 1,
                                'debit': amount < 0.0 and -amount or 0.0,
                                'credit': amount > 0.0 and amount or 0.0,
                                'account_id': tax['account_id'],
                                'tax_line_id': tax['id'],
                                'tax_ids': [(4, rec.stamp_tax.id)],
                                'tax_repartition_line_id': tax['tax_repartition_line_id'],
                                'move_id': self._origin,
                                'date': self.date,
                                'exclude_from_invoice_tab': True,
                                'partner_id': terms_lines.partner_id.id,
                                'company_id': terms_lines.company_id.id,
                                # 'company_currency_id': terms_lines.company_currency_id.id,
                            }
                            if self.move_type == "out_invoice":
                                dict.update({
                                    'debit': amount < 0.0 and -amount or 0.0,
                                    'credit': amount > 0.0 and amount or 0.0,
                                })
                            else:
                                dict.update({
                                    'debit': amount > 0.0 and amount or 0.0,
                                    'credit': amount < 0.0 and -amount or 0.0,
                                })
                            if in_draft_mode:
                                self.line_ids += create_method(dict)
                                # Updation of Invoice Line Id
                                duplicate_id = self.invoice_line_ids.filtered(
                                    lambda line: line.name and line.name.find('Droit de Timbre') == 0)
                                self.invoice_line_ids = self.invoice_line_ids - duplicate_id
                            else:
                                dict.update({
                                    'price_unit': 0.0,
                                    'debit': 0.0,
                                    'credit': 0.0,
                                })
                                self.line_ids = [(0, 0, dict)]

                        if (self.move_type == "in_invoice"
                                     or self.move_type == "in_refund"):
                            dict = {
                                'move_name': self.name,
                                'name': name,
                                'price_unit':amount,
                                'quantity': 1,
                                'debit': amount > 0.0 and amount or 0.0,
                                'credit': amount < 0.0 and -amount or 0.0,
                                'account_id': tax['account_id'],
                                'tax_line_id': tax['id'],
                                'tax_ids': [(4, rec.stamp_tax.id)],
                                'tax_repartition_line_id': tax['tax_repartition_line_id'],
                                'move_id': self.id,
                                'date': self.date,
                                'exclude_from_invoice_tab': True,
                                'partner_id': terms_lines.partner_id.id,
                                'company_id': terms_lines.company_id.id,
                                # 'company_currency_id': terms_lines.company_currency_id.id,
                            }

                            if self.move_type == "in_invoice":
                                dict.update({
                                    'debit': amount > 0.0 and amount or 0.0,
                                    'credit': amount < 0.0 and -amount or 0.0,
                                })
                            else:
                                dict.update({
                                    'debit': amount < 0.0 and -amount or 0.0,
                                    'credit': amount > 0.0 and amount or 0.0,
                                })
                            self.line_ids += create_method(dict)
                            # updation of invoice line id
                            duplicate_id = self.invoice_line_ids.filtered(
                                lambda line: line.name and line.name.find('Droit de Timbre') == 0)
                            self.invoice_line_ids = self.invoice_line_ids - duplicate_id

                    if in_draft_mode:
                        # Update the payement account amount
                        terms_lines = self.line_ids.filtered(
                            lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
                        other_lines = self.line_ids.filtered(
                            lambda line: line.account_id.user_type_id.type not in ('receivable', 'payable'))
                        total_balance = sum(other_lines.mapped('balance'))
                        total_amount_currency = sum(other_lines.mapped('amount_currency'))
                        terms_lines.update({
                            'amount_currency': -total_amount_currency,
                            'debit': total_balance < 0.0 and -total_balance or 0.0,
                            'credit': total_balance > 0.0 and total_balance or 0.0,
                        })
                    else:
                        terms_lines = self.line_ids.filtered(
                            lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
                        other_lines = self.line_ids.filtered(
                            lambda line: line.account_id.user_type_id.type not in ('receivable', 'payable'))
                        stamp_lines = self.line_ids.filtered(
                            lambda line: line.name and line.name.find('Droit de Timbre') == 0)
                        total_balance = sum(other_lines.mapped('balance')) - amount
                        total_amount_currency = sum(other_lines.mapped('amount_currency'))
                        dict1 = {
                            'debit': amount < 0.0 and -amount or 0.0,
                            'credit': amount > 0.0 and amount or 0.0,
                        }
                        dict2 = {
                            'debit': total_balance < 0.0 and -total_balance or 0.0,
                            'credit': total_balance > 0.0 and total_balance or 0.0,
                        }
                        self.line_ids = [(1, stamp_lines.id, dict1), (1, terms_lines.id, dict2)]
                        print()

            elif not rec.stamp_tax:
                stamp_lines = rec.line_ids.filtered(
                    lambda line: line.name and line.name.find('Droit de Timbre') == 0)
                if stamp_lines:
                    for line in stamp_lines:
                        rec.line_ids -= line

    def _recompute_tax_lines(self, recompute_tax_base_amount=False):
        super(InvoiceStampTax, self)._recompute_tax_lines(recompute_tax_base_amount=False)
        self._recompute_stamp_tax_lines()
