# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 Alda Hotels <informatica@aldahotels.com>
#                       Jose Luis Algara <osotranquilo@gmail.com>
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
import base64  
import datetime

import logging
_logger=logging.getLogger(__name__)


class Wizard(models.TransientModel):
    _name = 'police.wizard'

    download_date = fields.Date('Date',required=True)
    download_num = fields.Char('Correlative number',required=True,size=3,help='Number provided by the police')
    txt_filename = fields.Char()
    txt_binary = fields.Binary()

    @api.one
    def generate_file(self):
        compa = self.env.user.company_id
        compapolice = 'NoValid'
        if compa.police <> False:
            compapolice = compa.police      
        lines = self.env['cardex'].search([('enter_date','=',self.download_date)])
        content = "1|"+compapolice+"|"
        content += datetime.datetime.now().strftime("%Y%m%d|%H%M")
        content += "|"+str(len(lines))+ """
"""
        for line in lines :
            if  line.partner_id.documenttype in ["D","P","C"]:
                content += "2|"+line.partner_id.poldocument + "||"
            else:
                content += "2||"+line.partner_id.poldocument + "|"
            content += line.partner_id.documenttype + "|"
            content += datetime.datetime.strptime(line.partner_id.polexpedition, "%Y-%m-%d").date().strftime("%Y%m%d") + "|"
            content += line.partner_id.firstname.upper() + "|"
            apellidos = line.partner_id.lastname.split(" ", 1)
            #_logger.info(line.partner_id.lastname)
            #_logger.info(apellidos[0])
            if len(apellidos) == 2:
                content += apellidos[0].upper() + "|"
                content += apellidos[1].upper() + "|"
            else:
                content += apellidos[0].upper() + "||"

            content += line.partner_id.gender.upper()[0] + "|"
            content += datetime.datetime.strptime(line.partner_id.birthdate_date, "%Y-%m-%d").date().strftime("%Y%m%d") + "|"
            content += line.partner_id.code_ine.name.upper() + "|"
            content += datetime.datetime.strptime(line.enter_date, "%Y-%m-%d").date().strftime("%Y%m%d") + "|"

            content += """
"""

        return self.write({
            'txt_filename': compapolice +'.'+ self.download_num,
            'txt_binary': base64.encodestring(content)
            })