# -*- coding: utf-8 -*-
# © 2017 Comunitea
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, api
from odoo.exceptions import AccessError


class AccountInvoice(models.Model):

    _inherit = 'account.invoice'

    @api.multi
    def _add_supplier_to_product(self):
        # Add the partner in the supplier list of the product if the supplier
        # is not registered for this product. We limit to 10 the number of
        # suppliers for a product to avoid the mess that
        # could be caused for some generic products ("Miscellaneous").
        for line in self.invoice_line_ids.filtered(lambda r: r.product_id):
            # Do not add a contact as a supplier
            partner = self.partner_id if not self.partner_id.parent_id else \
                self.partner_id.parent_id
            if partner not in line.product_id.seller_ids.mapped('name') and \
                    len(line.product_id.seller_ids) <= 10:
                currency = partner.property_purchase_currency_id or \
                    self.env.user.company_id.currency_id
                supplierinfo = {
                    'name': partner.id,
                    'sequence':
                        max(line.product_id.seller_ids.mapped('sequence')) + 1
                        if line.product_id.seller_ids else 1,
                    'product_uom': line.uom_id.id,
                    'min_qty': 0.0,
                    'price':
                        self.currency_id.compute(line.price_unit, currency),
                    'currency_id': currency.id,
                    'delay': 0,
                }
                vals = {
                    'seller_ids': [(0, 0, supplierinfo)],
                }
                try:
                    line.product_id.write(vals)
                except AccessError:  # no write access rights -> just ignore
                    break
            else:
                currency = partner.property_purchase_currency_id or \
                    self.env.user.company_id.currency_id
                seller_id = line.product_id.seller_ids.filtered(
                    lambda x: x.name == partner)
                try:
                    seller_id.write(
                        {'price':
                         self.currency_id.compute(line.price_unit, currency)})
                except AccessError:  # no write access rights -> just ignore
                    break

    @api.multi
    def action_invoice_open(self):
        res = super(AccountInvoice, self).action_invoice_open()
        if self.type == 'in_invoice':
            self._add_supplier_to_product()
        return res
