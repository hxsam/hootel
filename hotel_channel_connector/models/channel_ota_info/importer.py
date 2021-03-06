# Copyright 2018 Alexandre Díaz <dev@redneboa.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.addons.component.core import Component
from odoo.addons.hotel_channel_connector.components.core import ChannelConnectorError
from odoo.addons.connector.components.mapper import mapping
from odoo import fields, api, _
from odoo.tools import (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT)


class ChannelOtaInfoImporter(Component):
    _name = 'channel.ota.info.importer'
    _inherit = 'hotel.channel.importer'
    _apply_on = ['channel.ota.info']
    _usage = 'ota.info.importer'

    @api.model
    def import_otas_info(self):
        count = 0
        try:
            results = self.backend_adapter.get_channels_info()

            channel_ota_info_obj = self.env['channel.ota.info']
            ota_info_mapper = self.component(usage='import.mapper',
                                             model_name='channel.ota.info')
            for ota_id in results.keys():
                vals = {
                    'id': ota_id,
                    'name': results[ota_id]['name'],
                    'ical': results[ota_id]['ical'] == 1,
                }
                map_record = ota_info_mapper.map_record(vals)
                ota_info_bind = channel_ota_info_obj.search([
                    ('ota_id', '=', ota_id)
                ], limit=1)
                if ota_info_bind:
                    ota_info_bind.write(map_record.values())
                else:
                    ota_info_bind.create(map_record.values(for_create=True))
                count = count + 1
        except ChannelConnectorError as err:
            self.create_issue('room', _("Can't import rooms from WuBook"), err.data['message'])
        return count


class ChannelOtaInfoImportMapper(Component):
    _name = 'channel.ota.info.import.mapper'
    _inherit = 'channel.import.mapper'
    _apply_on = 'channel.ota.info'

    direct = [
        ('id', 'ota_id'),
        ('name', 'name'),
        ('ical', 'ical'),
    ]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}
