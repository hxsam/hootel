# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import xmlrpclib
from datetime import datetime
from urlparse import urljoin
from openerp import models, api
from openerp.exceptions import except_orm, UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

def _partner_split_name(partner_name):
    return [' '.join(partner_name.split()[:-1]), ' '.join(partner_name.split()[-1:])]

class WuBook(models.TransientModel):
    _name = 'wubook'

    def __init__(self, pool, cr):
        init_res = super(WuBook, self).__init__(pool, cr)
        self.SERVER = False
        self.LCODE = False
        self.TOKEN = False
        return init_res

    def init_connection_(self):
        user_r = self.env['res.users'].browse(self.env.uid)

        user = user_r.partner_id.wubook_user
        passwd = user_r.partner_id.wubook_passwd
        self.LCODE = user_r.partner_id.wubook_lcode
        pkey = user_r.partner_id.wubook_pkey
        server_addr = user_r.partner_id.wubook_server

        self.SERVER = xmlrpclib.Server(server_addr)
        res, tok = self.SERVER.acquire_token(user, passwd, pkey)
        self.TOKEN = tok
        
        if res != 0:
            raise UserError("Can't connect with WuBook!")
        
        return True

    def close_connection_(self):
        self.SERVER.release_token(self.TOKEN)
        self.TOKEN = False
        self.SERVER = False

    @api.multi
    def create_room(self, vals):
        isConnected = self.init_connection_()
        if not isConnected:
            return False

        shortcode = self.env['ir.sequence'].get('seq_vroom_id')
        
        _logger.info("CREANDO HABITACION!: %s" % shortcode)

        res, rid = self.SERVER.new_room(
            self.TOKEN,
            self.LCODE,
            0,
            vals['name'],
            2,
            vals['list_price'],
            'max_real_rooms' in vals and vals['max_real_rooms'] or 1,
            shortcode[:4],
            'nb'
            #rtype=('name' in vals and vals['name'] and 3) or 1
        )

        self.close_connection_()

        if res == 0:
            vals.update({'wrid': rid})
        else:
            raise UserError("Can't create room in WuBook!")
        return vals

    @api.multi
    def modify_room(self, vroomid):
        isConnected = self.init_connection_()
        if not isConnected:
            return False

        vroom = self.env['hotel.virtual.room'].browse([vroomid])

        res, rid = self.SERVER.mod_room(
            self.TOKEN,
            self.LCODE,
            vroom.wrid,
            vroom.name,
            2,
            vroom.list_price,
            vroom.max_real_rooms,
            vroom.wscode,
            'nb'
            #rtype=('name' in vals and vals['name'] and 3) or 1
        )

        self.close_connection_()
        
        if res != 0:
            raise UserError("Can't modify room in WuBook!")
        
        return True
    
    @api.multi
    def delete_room(self, vroomid):
        isConnected = self.init_connection_()
        if not isConnected:
            return False

        vroom = self.env['hotel.virtual.room'].browse([vroomid])

        res, rid = self.SERVER.del_room(
            self.TOKEN,
            self.LCODE,
            vroom.wrid
        )

        self.close_connection_()
        
        if res != 0:
            raise UserError("Can't delete room in WuBook!")
        
        return True
    
    @api.multi
    def import_rooms(self):
        isConnected = self.init_connection_()
        if not isConnected:
            return False

        res, rooms = self.SERVER.fetch_rooms(
            self.TOKEN,
            self.LCODE,
            0
        )
        
        self.close_connection_()
        
        vroom_obj = self.env['hotel.virtual.room']
        
        if res == 0:
            for room in rooms:
                vroom = vroom_obj.search([('wrid', '=', room['id'])], limit=1)
                vals = {
                    'name': room['name'],
                    'wrid': room['id'],
                    'wscode': room['shortname'],
                    'list_price': room['price'],                    
                }
                if vroom:
                    vroom.write(vals, check=False)
                else:
                    vroom_obj.create(vals, check=False)
        else:
            raise UserError("Can't import rooms from WuBook!")
        
        return True

    @api.multi
    def push_prices(self):

        if True:
            return True

        isConnected = self.init_connection_()
        if not isConnected:
            return False

        vroom = self.env['hotel.virtual.room'].browse([])

        res, rid = self.SERVER.mod_room(
            self.TOKEN,
            self.LCODE,
            vroom.wrid,
            vroom.name,
            2,
            vroom.list_price,
            vroom.max_real_rooms,
            vroom.wscode,
            'nb'
            #rtype=('name' in vals and vals['name'] and 3) or 1
        )

        self.close_connection_()
        return True

    @api.multi
    def push_activation(self):
        isConnected = self.init_connection_()
        if not isConnected:
            return False

        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        res = self.SERVER.push_activation(self.TOKEN,
                                          self.LCODE,
                                          urljoin(base_url, "/wubook/push"), 1)

        self.close_connection_()
        return True

    @api.multi
    def corporate_fetch(self):
        isConnected = self.init_connection_()
        if not isConnected:
            return False

        res = self.SERVER.corporate_fetchable_properties(self.TOKEN)

        self.close_connection_()
        return True

    @api.multi
    def fetch_new_bookings(self):
        isConnected = self.init_connection_()
        if not isConnected:
            return False

        res, bookings = self.SERVER.fetch_new_bookings(self.TOKEN,
                                                       self.LCODE,
                                                       1,
                                                       0)
        _logger.info("FETCH NEW BOOKINGS")
        _logger.info(res)
        _logger.info(bookings)

        self.close_connection_()
        return True

    @api.multi
    def initialize(self):
        _logger.info("INITIALIZE WUBOOK")
        noErrors = self.push_activation()
        if noErrors:
            noErrors = self.fetch_new_bookings()
        return noErrors
    
    # TODO: Saber a que habitacion virtual pertenece la reserva de una real
    @api.multi
    def create_reservation(self, reservid):
        isConnected = self.init_connection_()
        if not isConnected:
            return False

        reserv = self.env['hotel.reservation'].browse([reservid])

        vroom = self.env['hotel.virtual.room'].search([('product_id', '=', reserv.product_id.id)], limit=1)
        res, rcode = self.SERVER.new_reservation(self.TOKEN,
                                                 self.LCODE, 
                                                 reserv.checkin,
                                                 reserv.checkout,
                                                 { vroom.wrid: [reserv.adults+reserv.children, 'nb'] },
                                                 {
                                                    'lname': _partner_split_name(reserv.partner_id.name)[1],
                                                    'fname': _partner_split_name(reserv.partner_id.name)[0],
                                                    'email': reserv.partner_id.email,
                                                    'city': reserv.partner_id.city,
                                                    'phone': reserv.partner_id.phone,
                                                    'street': reserv.partner_id.street,
                                                    'country': reserv.partner_id.country_id.code,
                                                    'arrival_hour': datetime.strptime(reserv.checkin, "%H:%M:%S"),
                                                    'notes': '' # TODO: Falta poner el cajetin de observaciones en folio o reserva..
                                                 },
                                                 reserv.adults+reserv.children)

        self.close_connection_()
        
        reserv.write({'wrid': rcode})
        return True
    
    @api.multi
    def cancel_reservation(self, reservid, reason=""):
        isConnected = self.init_connection_()
        if not isConnected:
            return False

        reserv = self.env['hotel.reservation'].browse([reservid])
        
        res, rcode = self.SERVER.cancel_reservation(self.TOKEN,
                                                    self.LCODE,
                                                    reserv.wrid,
                                                    reason)
        
        self.close_connection_()
        
        if res != 0:
            raise UserError("Can't cancel reservation in WuBook!")
        
        return True