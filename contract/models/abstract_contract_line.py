# Copyright 2004-2010 OpenERP SA
# Copyright 2014 Angel Moya <angel.moya@domatix.com>
# Copyright 2015 Pedro M. Baeza <pedro.baeza@tecnativa.com>
# Copyright 2016-2018 Carlos Dauden <carlos.dauden@tecnativa.com>
# Copyright 2016-2017 LasLabs Inc.
# Copyright 2018 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, fields
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class AccountAbstractAnalyticContractLine(models.AbstractModel):
    _name = 'account.abstract.analytic.contract.line'
    _description = 'Account Abstract Analytic Contract Line'

    product_id = fields.Many2one(
        'product.product', string='Product', required=True
    )

    name = fields.Text(string='Description', required=True)
    quantity = fields.Float(default=1.0, required=True)
    uom_id = fields.Many2one(
        'uom.uom', string='Unit of Measure', required=True
    )
    automatic_price = fields.Boolean(
        string="Auto-price?",
        help="If this is marked, the price will be obtained automatically "
        "applying the pricelist to the product. If not, you will be "
        "able to introduce a manual price",
    )
    specific_price = fields.Float(string='Specific Price')
    price_unit = fields.Float(
        string='Unit Price',
        compute="_compute_price_unit",
        inverse="_inverse_price_unit",
    )
    price_subtotal = fields.Float(
        compute='_compute_price_subtotal',
        digits=dp.get_precision('Account'),
        string='Sub Total',
    )
    discount = fields.Float(
        string='Discount (%)',
        digits=dp.get_precision('Discount'),
        help='Discount that is applied in generated invoices.'
        ' It should be less or equal to 100',
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Sequence of the contract line when displaying contracts",
    )
    recurring_rule_type = fields.Selection(
        [
            ('daily', 'Day(s)'),
            ('weekly', 'Week(s)'),
            ('monthly', 'Month(s)'),
            ('monthlylastday', 'Month(s) last day'),
            ('yearly', 'Year(s)'),
        ],
        default='monthly',
        string='Recurrence',
        help="Specify Interval for automatic invoice generation.",
        required=True,
    )
    recurring_invoicing_type = fields.Selection(
        [('pre-paid', 'Pre-paid'), ('post-paid', 'Post-paid')],
        default='pre-paid',
        string='Invoicing type',
        help="Specify if process date is 'from' or 'to' invoicing date",
        required=True,
    )
    recurring_interval = fields.Integer(
        default=1,
        string='Repeat Every',
        help="Repeat every (Days/Week/Month/Year)",
        required=True,
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner", string="Partner (always False)"
    )
    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist', string='Pricelist'
    )
    recurring_next_date = fields.Date(
        default=fields.Date.context_today,
        copy=False,
        string='Date of Next Invoice',
    )

    @api.depends(
        'automatic_price',
        'specific_price',
        'product_id',
        'quantity',
        'pricelist_id',
        'partner_id',
    )
    def _compute_price_unit(self):
        """Get the specific price if no auto-price, and the price obtained
        from the pricelist otherwise.
        """
        for line in self:
            if line.automatic_price:
                product = line.product_id.with_context(
                    quantity=line.env.context.get(
                        'contract_line_qty', line.quantity
                    ),
                    pricelist=line.pricelist_id.id,
                    partner=line.partner_id.id,
                    date=line.env.context.get('old_date', fields.Date.today()),
                )
                line.price_unit = product.price
            else:
                line.price_unit = line.specific_price

    # Tip in https://github.com/odoo/odoo/issues/23891#issuecomment-376910788
    @api.onchange('price_unit')
    def _inverse_price_unit(self):
        """Store the specific price in the no auto-price records."""
        for line in self.filtered(lambda x: not x.automatic_price):
            line.specific_price = line.price_unit

    @api.multi
    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_price_subtotal(self):
        for line in self:
            subtotal = line.quantity * line.price_unit
            discount = line.discount / 100
            subtotal *= 1 - discount
            if line.pricelist_id:
                cur = line.pricelist_id.currency_id
                line.price_subtotal = cur.round(subtotal)
            else:
                line.price_subtotal = subtotal

    @api.multi
    @api.constrains('discount')
    def _check_discount(self):
        for line in self:
            if line.discount > 100:
                raise ValidationError(
                    _("Discount should be less or equal to 100")
                )

    @api.multi
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return {'domain': {'uom_id': []}}

        vals = {}
        domain = {
            'uom_id': [
                ('category_id', '=', self.product_id.uom_id.category_id.id)
            ]
        }
        if not self.uom_id or (
            self.product_id.uom_id.category_id.id != self.uom_id.category_id.id
        ):
            vals['uom_id'] = self.product_id.uom_id

        date = self.recurring_next_date or fields.Date.today()
        partner = self.partner_id or self.env.user.partner_id

        product = self.product_id.with_context(
            lang=partner.lang,
            partner=partner.id,
            quantity=self.quantity,
            date=date,
            pricelist=self.pricelist_id.id,
            uom=self.uom_id.id,
        )

        name = product.name_get()[0][1]
        if product.description_sale:
            name += '\n' + product.description_sale
        vals['name'] = name

        vals['price_unit'] = product.price
        self.update(vals)
        return {'domain': domain}