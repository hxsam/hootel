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
from openerp import models, fields, api


class VirtualRoomAvailability(models.Model):
    _inherit = 'hotel.virtual.room.availabity'

    wpushed = fields.Boolean("WuBook Pushed", readonly=True, default=False)

    @api.multi
    def write(self, vals):
        if self._context.get('wubook_action', True):
            vals.update({'wpushed': False})
        return super(VirtualRoomAvailability, self).write(vals)
