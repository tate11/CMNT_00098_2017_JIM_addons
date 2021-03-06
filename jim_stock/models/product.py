# -*- coding: utf-8 -*-
# © 2016 Comunitea - Javier Colmenero <javier@comunitea.com>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import fields, models, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from odoo.addons.stock.models.product import OPERATORS


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _search_global_real_stock(self, operator, value):
        domain = [('global_real_stock', operator, value)]
        product_variant_ids = self.env['product.product'].search(domain)
        return [('product_variant_ids', 'in', product_variant_ids.ids)]

    def _search_global_avail_stock(self, operator, value):
        domain = [('global_available_stock', operator, value)]
        product_variant_ids = self.env['product.product'].search(domain)
        return [('product_variant_ids', 'in', product_variant_ids.ids)]

    global_real_stock = fields.Float('Global Real Stock',
                                     compute='_compute_global_stock',
                                     digits=dp.get_precision
                                     ('Product Unit of Measure'),
                                     help="Real stock in all companies.",
                                     search='_search_global_real_stock')
    global_available_stock = fields.Float('Global Available Stock',
                                          compute='_compute_global_stock',
                                          digits=dp.get_precision
                                          ('Product Unit of Measure'),
                                          help="Real stock minus outgoing "
                                          " in all companies.",
                                          search='_search_global_avail_stock')

    @api.multi
    def _compute_global_stock(self):
        for template in self:
            global_real_stock = 0.0
            global_available_stock = 0.0
            for p in template.product_variant_ids:
                global_real_stock += p.global_real_stock
                global_available_stock += p.global_available_stock
            template.global_real_stock = global_real_stock
            template.global_available_stock = global_available_stock


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _search_global_product_quantity(self, operator, value, field):
        if field not in ('global_available_stock', 'global_real_stock', 'web_global_stock'):
            raise UserError(_('Invalid domain left operand %s') % field)
        if operator not in ('<', '>', '=', '!=', '<=', '>='):
            raise UserError(_('Invalid domain operator %s') % operator)
        if not isinstance(value, (float, int)):
            raise UserError(_('Invalid domain right operand %s') % value)

        ids = []
        for product in self.search([]):
            if OPERATORS[operator](product[field], value):
                ids.append(product.id)
        return [('id', 'in', ids)]

    def _search_global_real_stock(self, operator, value):
        if value == 0.0 and operator in ('=', '>=', '<='):
            return self._search_global_product_quantity(operator, value,
                                                        'global_real_stock')

    def _search_global_avail_stock(self, operator, value):
        return self.\
            _search_global_product_quantity(operator, value,
                                            'global_available_stock')

    def _search_web_global_stock(self, operator, value):
        return self._search_global_product_quantity(operator, value,
                                                        'web_global_stock')

    global_real_stock = fields.Float('Global Real Stock',
                                     compute='_compute_global_stock',
                                     digits=dp.get_precision
                                     ('Product Unit of Measure'),
                                     help="Real stock in all companies.",
                                     search='_search_global_real_stock')
    global_available_stock = fields.Float('Global Available Stock',
                                          compute='_compute_global_stock',
                                          digits=dp.get_precision
                                          ('Product Unit of Measure'),
                                          help="Real stock minus outgoing "
                                          " in all companies.",
                                          search='_search_global_avail_stock')
    web_global_stock = fields.Float('Web stock', readonly=True,
                                    digits=dp.get_precision
                                    ('Product Unit of Measure'),
                                    compute="_compute_global_stock")

    @api.multi
    def _calculate_globals(self):
        not_deposit_ids = \
            self.env['stock.location'].sudo().search(
                [('deposit', '!=', True), ('usage', '=', 'internal')]).ids
        company_ids = \
            self.env['res.company'].sudo().search(
                [('no_stock', '=', True)]).ids
        self._cr.execute(
            "SELECT SOL.product_id, sum(SOL.product_uom_qty) as qty FROM "
            "sale_order_line SOL "
            "INNER JOIN sale_order  SO ON SO.id = SOL.order_id "
            "INNER JOIN stock_location_route SLR  ON SLR.id = SOL.route_id "
            "WHERE SOL.product_id in %s "
            "AND SO.state in ('lqdr', 'pending', 'progress_lqdr', 'progress',"
            " 'proforma') "
            "AND not SLR.no_stock AND SO.company_id NOT IN %s "
            "group BY SOL.product_id", [tuple(self.ids), tuple(company_ids)])
        sale_line_data = dict(self._cr.fetchall())

        ctx = self._context.copy()
        ctx.update({'location': not_deposit_ids})
        qty_available_d = dict(
            [(p['id'], p['qty_available'])
             for p in self.with_context(ctx).sudo().read(['qty_available'])])
        ctx.update({'no_move_ic': True})
        outgoing_qty_d = dict(
            [(p['id'], p['outgoing_qty'])
             for p in self.with_context(ctx).sudo().read(['outgoing_qty'])])
        global_real_stock = qty_available_d
        global_available_stock = dict(
            [(p, qty_available_d[p] - outgoing_qty_d[p])
             for p in qty_available_d.keys()])

        company_real_stock = dict([(x.id, 0) for x in self])
        company_available_stock = dict([(x.id, 0) for x in self])
        if company_ids:
            for company in company_ids:
                ctx.update({'force_company': company})
                company_available = dict(
                    [(p['id'], p['qty_available']) for p in
                     self.with_context(ctx).sudo().read(['qty_available'])])
                company_outgoing = dict(
                    [(p['id'], p['outgoing_qty']) for p in
                     self.with_context(ctx).sudo().read(['outgoing_qty'])])

                company_real_stock = {
                    k: company_real_stock.get(k, 0) +
                    company_available.get(k, 0)
                    for k in set(company_real_stock) | set(company_available)}

                company_available_stock_ = dict(
                    [(p, company_available[p] - company_outgoing[p])
                     for p in company_available.keys()])
                company_available_stock = {
                    k: company_available_stock.get(k, 0) +
                    company_available_stock_.get(k, 0)
                    for k in set(company_available_stock) |
                    set(company_available_stock_)}
        a = dict([(p, global_real_stock[p] -
                   company_real_stock[p])for p in self.ids if p in global_available_stock.keys()])
        b = dict([
            (p, global_available_stock[p] - sale_line_data.get(p, 0) -
             company_available_stock[p])for p in self.ids if p in global_available_stock.keys()])
        return dict(
            [(p, {'global_real_stock': a[p],
                  'global_available_stock': b[p]}) for p in self.ids if p in global_available_stock.keys()])

    def _compute_global_stock(self):
        res = self._calculate_globals()
        bom_obj = self.env["mrp.bom"]
        bom_line_obj = self.env["mrp.bom.line"]
        for product in self.filtered(lambda x: x.id in res.keys()):
            product.global_real_stock = res[product.id]['global_real_stock']
            product.global_available_stock = \
                res[product.id]['global_available_stock']
            stock = res[product.id]['global_available_stock']
            if product.bom_count:
                boms = \
                    bom_obj.search(['|', '&',
                                    ('product_tmpl_id', '=',
                                     product.product_tmpl_id.id),
                                    ('product_id', '=', False),
                                    ('product_id', '=', product.id)])
                for bom in boms:
                    min_qty = False
                    for line in bom.bom_line_ids:
                        if line.product_id.id in res:
                            global_available_stock = \
                                res[line.product_id.id][
                                  'global_available_stock']
                        else:
                            global_available_stock = \
                                line.product_id._calculate_globals()[
                                 line.product_id.id]['global_available_stock']
                        qty = global_available_stock / line.product_qty
                        if isinstance(min_qty, bool) or qty < min_qty:
                            min_qty = qty
                    if not min_qty or min_qty < 0:
                        min_qty = 0
                    stock += (min_qty * bom.product_qty)
            else:
                bom_lines = bom_line_obj.\
                    search([('product_id', '=', product.id),
                            ('bom_id.no_web_stock', '=', False)])
                for line in bom_lines:
                    if line.product_qty:
                        variants = line.bom_id.product_id or \
                            line.bom_id.product_tmpl_id.product_variant_ids
                        global_available_stock = sum(
                            [res[x.id]['global_available_stock']
                             if x in res
                             else x._calculate_globals()[x.id]
                             ['global_available_stock']
                             for x in variants])
                        stock += global_available_stock * line.product_qty
            product.web_global_stock = int(stock)

    def _get_domain_locations(self):
        if self._context.get('no_move_ic'):
            domain_quant_loc, domain_move_in_loc, domain_move_out_loc = super(ProductProduct, self)._get_domain_locations()
            domain_move_out_loc = [('move_dest_IC_id', '=', False)] + domain_move_out_loc
            return domain_quant_loc, domain_move_in_loc, domain_move_out_loc
        else:
            return super(ProductProduct, self)._get_domain_locations()

    @api.multi
    def move_stock_import(self, location, qty, cost, date, company, in_out_type):
        self.ensure_one()
        self_date_context = self.with_context(create_date=date)
        move_vals = {
            'name': self.name,
            'product_id': self.id,
            'product_uom': self.uom_id.id,
            'product_uom_qty': qty,
            'date': date,
            'state': 'confirmed',
            'company_id': company.id
        }

        if in_out_type == 'out':
            customer_location_id = self.env.ref(
                'stock.stock_location_customers').id
            move_vals['location_id'] = location.id
            move_vals['location_dest_id'] = customer_location_id
        else:
            inventory_location_id = self.env.ref('stock.location_inventory').id
            move_vals['location_id'] = inventory_location_id
            move_vals['location_dest_id'] = location.id
        move = self_date_context.sudo().env['stock.move'].create(move_vals)

        if in_out_type == 'out':
            location_quants = self.env['stock.quant'].search(
                [('product_id', '=', self.id), ('location_id', '=', location.id),
                 ('company_id', '=', company.id),
                 ('reservation_id', '=', False), ('qty', '>', 0)],
                order='in_date asc')
            unnasigned_qty = qty
            quants = []
            for quant in location_quants:
                if not unnasigned_qty:
                    break
                if quant.qty < unnasigned_qty:
                    quants.append((quant, quant.qty))
                    unnasigned_qty -= quant.qty
                else:
                    quants.append((quant, unnasigned_qty))
                    unnasigned_qty = 0
            if unnasigned_qty:
                quants.append((None, unnasigned_qty))
            self_date_context.env['stock.quant'].quants_reserve(quants, move)
            if move.state != 'assigned':
                move.state = 'assigned'
            # No llamamos a action_done, debido a que al reservar los quants
            # manualmente falla
            self_date_context.env['stock.quant'].quants_move(
                quants, move, move.location_dest_id)
            move.quants_unreserve()
            move.write({'state': 'done', 'date': date, 'date_expected': date})
        else:
            move.sudo().action_done()
            move.sudo().write({'date': date, 'date_expected': date})
