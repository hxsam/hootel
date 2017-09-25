# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 Solucións Aloxa S.L. <info@aloxa.eu>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp.exceptions import ValidationError
from datetime import datetime, timedelta
from openerp import models, fields, api
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT


class MassiveChangesWizard(models.TransientModel):
    _name = 'wubook.wizard.massive.changes'

    # Common fields
    section = fields.Selection([
        ('0', 'Availability'),
        ('1', 'Restrictions'),
        ('2', 'Pricelist'),
    ], string='Section', default='0')
    date_start = fields.Datetime('Start Date', required=True)
    date_end = fields.Datetime('End Date', required=True)
    dmo = fields.Boolean('Monday', default=True)
    dtu = fields.Boolean('Tuesday', default=True)
    dwe = fields.Boolean('Wednesday', default=True)
    dth = fields.Boolean('Thursday', default=True)
    dfr = fields.Boolean('Friday', default=True)
    dsa = fields.Boolean('Saturday', default=True)
    dsu = fields.Boolean('Sunday', default=True)
    applied_on = fields.Selection([
        ('0', 'Global'),
        ('1', 'Specific'),
    ], string='Applied On', default='0')
    virtual_room_ids = fields.Many2many('hotel.virtual.room', string="Virtual Rooms")

    # Availability fields
    change_avail = fields.Boolean(default=False)
    avail = fields.Integer('Avail', default=0)
    change_no_ota = fields.Boolean(default=False)
    no_ota = fields.Boolean('No OTA', default=False)

    # Restriction fields
    restriction_id = fields.Many2one('reservation.restriction', 'Restriction Plan')
    change_min_stay = fields.Boolean(default=False)
    min_stay = fields.Integer("Min. Stay")
    change_min_stay_arrival = fields.Boolean(default=False)
    min_stay_arrival = fields.Integer("Min. Stay Arrival")
    change_max_stay = fields.Boolean(default=False)
    max_stay = fields.Integer("Max. Stay")
    change_closed = fields.Boolean(default=False)
    closed = fields.Boolean('Closed')
    change_closed_departure = fields.Boolean(default=False)
    closed_departure = fields.Boolean('Closed Departure')
    change_closed_arrival = fields.Boolean(default=False)
    closed_arrival = fields.Boolean('Closed Arrival')

    # Pricelist fields
    pricelist_id = fields.Many2one('product.pricelist', 'Pricelist')
    price = fields.Char('Price', help="Can use '+','-' or '%'...\nExamples:\n ⚫ +12.3 \t> Increase the price in 12.3\n ⚫ -1.45% \t> Substract 1.45%\n ⚫ 45 \t\t> Sets the price to 45" )

    @api.multi
    def is_valid_date(self, chkdate):
        self.ensure_one()
        date_start_dt = fields.Datetime.from_string(self.date_start)
        date_end_dt = fields.Datetime.from_string(self.date_end)
        wday = chkdate.timetuple()[6]
        wedays = [self.dmo, self.dtu, self.dwe, self.dth, self.dfr, self.dsa, self.dsu]
        return (chkdate >= self.date_start and chkdate <= self.date_end and wedays[wday])

    @api.multi
    def massive_change(self):
        for record in self:
            date_start_dt = fields.Datetime.from_string(record.date_start)
            date_end_dt = fields.Datetime.from_string(record.date_end)
            diff_days = abs((date_end_dt-date_start_dt).days)+1
            wedays = [record.dmo, record.dtu, record.dwe, record.dth, record.dfr, record.dsa, record.dsu]
            for i in range(0, diff_days):
                ndate = date_start_dt + timedelta(days=i)
                if not wedays[ndate.timetuple()[6]]:
                    continue
                if record.section == '0':
                    domain = [('date', '=', ndate.strftime(DEFAULT_SERVER_DATE_FORMAT))]
                    if record.applied_on == '1':
                        domain.append(('virtual_room_id', 'in', record.virtual_room_ids.ids))
                    vrooms = self.env['virtual.room.availability'].search(domain)
                    vals = {}
                    if record.change_avail:
                        vals.update({'avail': record.avail})
                    if record.change_no_ota:
                        vals.update({'no_ota': record.no_ota})
                    if any(vals):
                        vrooms.write(vals)
                elif record.section == '1':
                    domain = [
                        ('date_start', '>=', ndate.strftime(DEFAULT_SERVER_DATE_FORMAT)),
                        ('date_end', '<=', ndate.strftime(DEFAULT_SERVER_DATE_FORMAT)),
                        ('restriction_id', '=', record.restriction_id.id),
                    ]
                    if record.applied_on == '1':
                        domain.append(('virtual_room_id', 'in', record.virtual_room_ids.ids))
                    rresctriction_item_ids = self.env['reservation.restriction.item'].search(domain)
                    vals = {}
                    if record.change_min_stay:
                        vals.update({'min_stay': record.min_stay})
                    if record.change_min_stay_arrival:
                        vals.update({'min_stay_arrival': record.min_stay_arrival})
                    if record.change_max_stay:
                        vals.update({'max_stay': record.max_stay})
                    if record.change_closed:
                        vals.update({'closed': record.closed})
                    if record.change_closed_departure:
                        vals.update({'closed_departure': record.closed_departure})
                    if record.change_closed_arrival:
                        vals.update({'closed_arrival': record.closed_arrival})
                    if any(vals):
                        rresctriction_item_ids.write(vals)
                elif record.section == '2':
                    price = 0.0
                    operation = 'a'
                    if record.price[0] == '+' or record.price[0] == '-':
                        if record.price[-1] == '%':
                            price = float(record.price[1:-1])
                            operation = (ecord.price[0] == '+') and 'ap' or 'sp'
                        else:
                            price = float(record.price[1:])
                            operation = (ecord.price[0] == '+') and 'a' or 's'
                    else:
                        if record.price[-1] == '%':
                            price = float(record.price[:-1])
                            operation = 'np'
                        else:
                            price = float(record.price)
                            operation = 'n'

                    domain = [
                        ('pricelist_id', '=', record.pricelist_id.id),
                        ('date_start', '>=', ndate.strftime(DEFAULT_SERVER_DATE_FORMAT)),
                        ('date_end', '<=', ndate.strftime(DEFAULT_SERVER_DATE_FORMAT)),
                        ('compute_price', '=', 'fixed'),
                        ('applied_on', '=', '1_product'),
                    ]
                    if record.applied_on == '1':
                        product_tmpl_ids = record.virtual_room_ids.mapped('product_id.product_tmpl_id.id')
                        domain.append(('product_tmpl_id', '=', product_tmpl_ids))
                    pricelist_item_ids = self.env['product.pricelist.item'].search(domain)

                    if operation == 'a':
                        for pli in pricelist_item_ids:
                            pli_price = pli.fixed_price
                            pli.write({'fixed_price': pli_price + price})
                    elif operation == 'ap':
                        for pli in pricelist_item_ids:
                            pli_price = pli.fixed_price
                            pli.write({'fixed_price': pli_price + price * pli_price * 0.01})
                    elif operation == 's':
                        for pli in pricelist_item_ids:
                            pli_price = pli.fixed_price
                            pli.write({'fixed_price': pli_price - price})
                    elif operation == 'sp':
                        for pli in pricelist_item_ids:
                            pli_price = pli.fixed_price
                            pli.write({'fixed_price': pli_price - price * pli_price * 0.01})
                    elif operation == 'np':
                        for pli in pricelist_item_ids:
                            pli_price = pli.fixed_price
                            pli.write({'fixed_price': price * pli_price * 0.01})
                    else:
                        pricelist_item_ids.write({'fixed_price': price})


        return True