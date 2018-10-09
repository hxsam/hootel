# Copyright 2018  Pablo Q. Barriuso
# Copyright 2018  Alexandre Díaz
# Copyright 2018  Dario Lodeiros
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import wdb
import logging
import urllib.error
import odoorpc.odoo
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class HotelNode(models.Model):

    _inherit = ['project.project']

    _description = 'Centralized hotel management features'

    active = fields.Boolean('Active', default=True,
                            help='The active field allows you to hide the \
                            node without removing it.')
    sequence = fields.Integer('Sequence', default=0,
                              help='Gives the sequence order when displaying the list of Nodes.')

    odoo_version = fields.Char()
    odoo_host = fields.Char('Host', required=True,
                            help='Full URL to the host.')
    odoo_db = fields.Char('Database Name',
                          help='Odoo database name.')
    odoo_user = fields.Char('Username',
                            help='Odoo administration user.')
    odoo_password = fields.Char('Password',
                                help='Odoo password.')
    odoo_port = fields.Integer(string='TCP Port', default=443,
                               help='Specify the TCP port for the XML-RPC protocol.')
    odoo_protocol = fields.Selection([('jsonrpc', 'jsonrpc'), ('jsonrpc+ssl', 'jsonrpc+ssl')],
                                     'Protocol', required=True, default='jsonrpc+ssl')

    user_ids = fields.One2many('hotel.node.user', 'node_id',
                               'Users with access to this hotel')

    group_ids = fields.Many2many('hotel.node.group', 'hotel_node_group_rel', 'node_id', 'group_id',
                                 string='Access Groups')

    room_type_ids = fields.One2many('hotel.node.room.type', 'node_id',
                                    'Rooms Type in this hotel')
    room_ids = fields.One2many('hotel.node.room', 'node_id',
                               'Rooms in this hotel')

    @api.constrains('group_ids')
    def _check_group_version(self):
        """
        :raise: ValidationError
        """
        for node in self:
            domain = [('id', 'in', node.group_ids.ids), ('odoo_version', '!=', node.odoo_version)]
            invalid_groups = self.env["hotel.node.group"].search_count(domain)
            if invalid_groups > 0:
                msg = _("At least one group is not within the node version.") + " " + \
                      _("Odoo version of the node: %s") % node.odoo_version
                _logger.warning(msg)
                raise ValidationError(msg)

    _sql_constraints = [
        ('db_node_id_uniq', 'unique (odoo_db, id)',
         'The database name of the hotel must be unique within the Master Node!'),
    ]

    @api.model
    def create(self, vals):
        """
        :param dict vals: the model's fields as a dictionary
        :return: new hotel node record created.
        :raise: ValidationError
        """
        try:
            noderpc = odoorpc.ODOO(vals['odoo_host'], vals['odoo_protocol'], vals['odoo_port'])
            noderpc.login(vals['odoo_db'], vals['odoo_user'], vals['odoo_password'])

            vals.update({'odoo_version': noderpc.version})

        except (odoorpc.error.RPCError, odoorpc.error.InternalError, urllib.error.URLError) as err:
            raise ValidationError(err)
        else:
            node_id = super().create(vals)
            noderpc.logout()
            return node_id

    @api.multi
    def action_sync_from_node(self):
        self.ensure_one()
        try:
            noderpc = odoorpc.ODOO(self.odoo_host, self.odoo_protocol, self.odoo_port)
            noderpc.login(self.odoo_db, self.odoo_user, self.odoo_password)
        except (odoorpc.error.RPCError, odoorpc.error.InternalError, urllib.error.URLError) as err:
            raise ValidationError(err)

        # TODO synchronize only if write_date in remote node is newer ¿?
        try:
            vals = {}
            # import remote groups
            remote_groups = noderpc.env['ir.model.data'].search_read(
                [('model', '=', 'res.groups')],
                ['complete_name', 'display_name'])

            master_groups = self.env["hotel.node.group"].search_read(
                [('odoo_version', '=', self.odoo_version)], ['xml_id'])

            gui_ids = [r['id'] for r in master_groups]
            xml_ids = [r['xml_id'] for r in master_groups]

            group_ids = []
            for group in remote_groups:
                if group['complete_name'] in xml_ids:
                    idx = xml_ids.index(group['complete_name'])
                    group_ids.append((4, gui_ids[idx], 0))
                else:
                    group_ids.append((0, 0, {
                        'name': group['display_name'],
                        'xml_id': group['complete_name'],
                        'odoo_version': self.odoo_version,
                    }))
            vals.update({'group_ids': group_ids})

            self.write(vals)

        except (odoorpc.error.RPCError, odoorpc.error.InternalError, urllib.error.URLError) as err:
            raise ValidationError(err)

        try:
            vals = {}
            # import remote users
            # TODO Restrict users to hootel users
            remote_users = noderpc.env['res.users'].search_read(
                [('login', '!=', 'admin')],
                ['name', 'login', 'email', 'is_company', 'partner_id', 'groups_id', 'active'])

            master_users = self.env["hotel.node.user"].search_read(
                [('node_id', '=', self.id)], ['remote_user_id'])

            master_ids = [r['id'] for r in master_users]
            remote_ids = [r['remote_user_id'] for r in master_users]

            user_ids = []
            for user in remote_users:
                if user['id'] in remote_ids:
                    idx = remote_ids.index(user['id'])
                    user_ids.append((1, master_ids[idx], {
                        'name': user['name'],
                        'login': user['login'],
                        'email': user['email'],
                        'active': user['active'],
                        'remote_user_id': user['id'],
                    }))
                else:
                    partner = self.env['res.partner'].search([('email', '=', user['email'])])
                    if not partner:
                        partner = self.env['res.partner'].create({
                            'name': user['name'],
                            'is_company': False,
                            'email': user['email'],
                        })

                    user_ids.append((0, 0, {
                        'name': user['name'],
                        'login': user['login'],
                        'email': user['email'],
                        'active': user['active'],
                        'remote_user_id': user['id'],
                        'partner_id': partner.id,
                    }))
            vals.update({'user_ids': user_ids})

            self.with_context({
                    'is_synchronizing': True,
                }).write(vals)

        except (odoorpc.error.RPCError, odoorpc.error.InternalError, urllib.error.URLError) as err:
            raise ValidationError(err)

        try:
            vals = {}
            # import remote partners (exclude unconfirmed using DNI)

        except (odoorpc.error.RPCError, odoorpc.error.InternalError, urllib.error.URLError) as err:
            raise ValidationError(err)

        try:
            vals = {}
            # import remote room types
            # TODO Actually only work for hootel v2
            remote_room_types = noderpc.env['hotel.room.type'].search_read(
                [], ['name', 'active', 'sequence', 'room_ids'])

            master_room_types = self.env["hotel.node.room.type"].search_read(
                [('node_id', '=', self.id)], ['remote_room_type_id'])

            master_ids = [r['id'] for r in master_room_types]
            remote_ids = [r['remote_room_type_id'] for r in master_room_types]

            room_type_ids = []
            for room_type in remote_room_types:
                if room_type['id'] in remote_ids:
                    idx = remote_ids.index(room_type['id'])
                    room_type_ids.append((1, master_ids[idx], {
                        'name': room_type['name'],
                        'active': room_type['active'],
                        'sequence': room_type['sequence'],
                        'remote_room_type_id': room_type['id'],
                    }))
                else:
                    room_type_ids.append((0, 0, {
                        'name': room_type['name'],
                        'active': room_type['active'],
                        'sequence': room_type['sequence'],
                        'remote_room_type_id': room_type['id'],
                    }))
            vals.update({'room_type_ids': room_type_ids})

            self.write(vals)

        except (odoorpc.error.RPCError, odoorpc.error.InternalError, urllib.error.URLError) as err:
            raise ValidationError(err)

        try:
            vals = {}
            # import remote rooms
            # TODO Actually only work for hootel v2
            remote_rooms = noderpc.env['hotel.room'].search_read(
                [],
                ['name', 'active', 'sequence', 'capacity', 'room_type_id'])

            master_rooms = self.env["hotel.node.room"].search_read(
                [('node_id', '=', self.id)], ['remote_room_id'])

            master_ids = [r['id'] for r in master_rooms]
            remote_ids = [r['remote_room_id'] for r in master_rooms]

            room_ids = []
            for room in remote_rooms:
                room_type_id = self.env["hotel.node.room.type"].search(
                    [('node_id', '=', self.id),
                     ('remote_room_type_id', '=', room['room_type_id'][0])]) or None

                if room_type_id is None:
                    msg = _("Something was completely wrong for Remote Room ID: [%s]") % room['id']
                    _logger.critical(msg)
                    raise ValidationError(msg)

                if room['id'] in remote_ids:
                    idx = remote_ids.index(room['id'])
                    room_ids.append((1, master_ids[idx], {
                        'name': room['name'],
                        'active': room['active'],
                        'sequence': room['sequence'],
                        'capacity': room['capacity'],
                        'room_type_id': room_type_id.id,
                        'remote_room_id': room['id'],
                    }))
                else:
                    room_ids.append((0, 0, {
                        'name': room['name'],
                        'active': room['active'],
                        'sequence': room['sequence'],
                        'capacity': room['capacity'],
                        'room_type_id': room_type_id.id,
                        'remote_room_id': room['id'],
                    }))
            vals.update({'room_ids': room_ids})

            self.write(vals)

        except (odoorpc.error.RPCError, odoorpc.error.InternalError, urllib.error.URLError) as err:
            raise ValidationError(err)

        noderpc.logout()
        return True