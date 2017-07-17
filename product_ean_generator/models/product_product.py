# -*- coding: utf-8 -*-
# Copyright 2017 Kiko Sánchez, Comunitea Servicios Tecnológicos S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError


DEFAULT_PRE = "843540%"



class ProductTemplate(models.Model):

    _inherit = 'product.template'

    @api.multi
    def asign_barcode(self):
        for template in self:
            template.product_variant_ids.asign_barcode()


class ProductProduct(models.Model):

    _inherit = 'product.product'

    @api.multi
    def write(self, vals):
        # Comprobamos si hay movimientos. No podemos por el tema de Mecalux
        if vals.get('barcode', False):
            for product in self:
                if product.stock_move_ids:
                    raise ValidationError(_("You can change barcode because this product has moves"))
        return super(ProductProduct, self).write(vals)

    def next_barcode(self):
        sequence = self.env.ref('product_ean_generator.seq_product_ean_auto')
        EAN = sequence.next_by_id()
        #
        # sql_last_barcode = "select MAX(left(barcode,12)) from product_product " \
        #                   "where length(barcode)=13 and barcode like '%s'" % DEFAULT_PRE
        #
        # self.env.cr.execute(sql_last_barcode)
        # EAN = self.env.cr.fetchall()[0][0]
        EAN = str(int(EAN) + 1)
        iSum = 0
        for i in range(len(EAN) - 1, 0, -1):
            if i % 2 == 0:
                iSum += int(EAN[i])
            else:
                iSum += int(EAN[i]) * 3

        iCheckSum = (10 - (iSum % 10)) % 10
        return EAN + str(iCheckSum)

    @api.model
    def create(self, vals):
        barcode = vals.get('barcode', False)
        if barcode == 'ASIGNAR':
            vals['barcode'] = self.next_barcode()
        return super(ProductProduct, self).create(vals)


    @api.multi
    def asign_barcode(self):
        for product in self.filtered(lambda s: s.barcode == "ASIGNAR" or not s.barcode):
            product.barcode = product.next_barcode()
