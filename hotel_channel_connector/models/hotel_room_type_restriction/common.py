# Copyright 2018 Alexandre Díaz <dev@redneboa.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, fields
from odoo.exceptions import ValidationError
from odoo.addons.queue_job.job import job, related_action
from odoo.addons.component.core import Component
from odoo.addons.component_event import skip_if

class ChannelHotelRoomTypeRestriction(models.Model):
    _name = 'channel.hotel.room.type.restriction'
    _inherit = 'channel.binding'
    _inherits = {'hotel.room.type.restriction': 'odoo_id'}
    _description = 'Channel Hotel Room Type Restriction'

    odoo_id = fields.Many2one(comodel_name='hotel.room.type.restriction',
                              string='Hotel Virtual Room Restriction',
                              required=True,
                              ondelete='cascade')
    channel_plan_id = fields.Char("Channel Plan ID", readonly=True, old_name='wpid')
    is_daily_plan = fields.Boolean("Channel Daily Plan", default=True, old_name='wdaily_plan')

    @job(default_channel='root.channel')
    @related_action(action='related_action_unwrap_binding')
    @api.multi
    def create_plan(self):
        self.ensure_one()
        if self._context.get('channel_action', True):
            with self.backend_id.work_on(self._name) as work:
                adapter = work.component(usage='backend.adapter')
                try:
                    channel_plan_id = adapter.create_rplan(self.name)
                    if channel_plan_id:
                        self.channel_plan_id = channel_plan_id
                except ValidationError as e:
                    self.create_issue('room', "Can't create restriction plan on channel", "sss")

    @job(default_channel='root.channel')
    @related_action(action='related_action_unwrap_binding')
    @api.multi
    def update_plan_name(self):
        self.ensure_one()
        if self._context.get('channel_action', True):
            with self.backend_id.work_on(self._name) as work:
                adapter = work.component(usage='backend.adapter')
                try:
                    adapter.rename_rplan(self.channel_plan_id, self.name)
                except ValidationError as e:
                    self.create_issue('room', "Can't update restriction plan name on channel", "sss")

    @job(default_channel='root.channel')
    @related_action(action='related_action_unwrap_binding')
    @api.multi
    def delete_plan(self):
        self.ensure_one()
        if self._context.get('channel_action', True) and self.channel_room_id:
            with self.backend_id.work_on(self._name) as work:
                adapter = work.component(usage='backend.adapter')
                try:
                    adapter.delete_rplan(self.channel_plan_id)
                except ValidationError as e:
                    self.create_issue('room', "Can't delete restriction plan on channel", "sss")

    @job(default_channel='root.channel')
    @api.multi
    def import_restriction_plans(self):
        if self._context.get('channel_action', True):
            with self.backend_id.work_on(self._name) as work:
                importer = work.component(usage='channel.importer')
                return importer.import_restriction_plans()

class HotelRoomTypeRestriction(models.Model):
    _inherit = 'hotel.room.type.restriction'

    channel_bind_ids = fields.One2many(
        comodel_name='channel.hotel.room.type.restriction',
        inverse_name='odoo_id',
        string='Hotel Channel Connector Bindings')

    @api.multi
    @api.depends('name')
    def name_get(self):
        room_type_restriction_obj = self.env['hotel.room.type.restriction']
        org_names = super(HotelRoomTypeRestriction, self).name_get()
        names = []
        for name in org_names:
            restriction_id = room_type_restriction_obj.browse(name[0])
            if restriction_id.channel_bind_ids.channel_plan_id:
                names.append((name[0], '%s (WuBook)' % name[1]))
            else:
                names.append((name[0], name[1]))
        return names

class ChannelBindingHotelRoomTypeRestrictionListener(Component):
    _name = 'channel.binding.hotel.room.type.restriction.listener'
    _inherit = 'base.connector.listener'
    _apply_on = ['channel.hotel.room.type.restriction']

    @skip_if(lambda self, record, **kwargs: self.no_connector_export(record))
    def on_record_create(self, record, fields=None):
        record.with_delay(priority=20).create_plan()

    @skip_if(lambda self, record, **kwargs: self.no_connector_export(record))
    def on_record_unlink(self, record, fields=None):
        record.with_delay(priority=20).delete_plan()

    @skip_if(lambda self, record, **kwargs: self.no_connector_export(record))
    def on_record_write(self, record, fields=None):
        if 'name' in fields:
            record.with_delay(priority=20).update_plan_name()
