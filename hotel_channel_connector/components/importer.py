# Copyright 2018 Alexandre Díaz <dev@redneboa.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import pytz
import json
from datetime import timedelta
from odoo.exceptions import ValidationError
from odoo.addons.component.core import AbstractComponent, Component
from odoo.addons.hotel_channel_connector.components.core import ChannelConnectorError
from odoo.addons.hotel import date_utils
from odoo import _
from odoo.tools import (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT)
from .backend_adapter import (
    DEFAULT_WUBOOK_DATE_FORMAT,
    DEFAULT_WUBOOK_DATETIME_FORMAT,
    WUBOOK_STATUS_BAD)
from odoo import api
_logger = logging.getLogger(__name__)

class HotelChannelConnectorImporter(AbstractComponent):
    _name = 'hotel.channel.importer'
    _inherit = ['base.importer', 'base.hotel.channel.connector']
    _usage = 'channel.importer'

    @api.model
    def _get_room_values_availability(self, room_type_id, date_str, day_vals, set_max_avail):
        room_type_avail_obj = self.env['hotel.room.type.availability']
        room_type_avail = room_type_avail_obj.search([
            ('room_type_id', '=', room_type_id),
            ('date', '=', date_str)
        ], limit=1)
        vals = {
            'no_ota': day_vals.get('no_ota'),
            'booked': day_vals.get('booked'),
            'avail': day_vals.get('avail', 0),
            'wpushed': True,
        }
        if set_max_avail:
            vals.update({'max_avail': day_vals.get('avail', 0)})
        if room_type_avail:
            room_type_avail.with_context({
                'wubook_action': False,
            }).write(vals)
        else:
            vals.update({
                'room_type_id': room_type_id,
                'date': date_str,
            })
            room_type_avail_obj.with_context({
                'wubook_action': False,
                'mail_create_nosubscribe': True,
            }).create(vals)

    @api.model
    def _get_room_values_restrictions(self, restriction_plan_id, room_type_id, date_str, day_vals):
        room_type_restr_item_obj = self.env['hotel.room.type.restriction.item']
        room_type_restr = room_type_restr_item_obj.search([
            ('room_type_id', '=', room_type_id),
            ('applied_on', '=', '0_room_type'),
            ('date_start', '=', date_str),
            ('date_end', '=', date_str),
            ('restriction_id', '=', restriction_plan_id),
        ])
        vals = {
            'min_stay': int(day_vals.get('min_stay', 0)),
            'min_stay_arrival': int(day_vals.get(
                'min_stay_arrival',
                0)),
            'max_stay': int(day_vals.get('max_stay', 0)),
            'max_stay_arrival': int(day_vals.get(
                'max_stay_arrival',
                0)),
            'closed': int(day_vals.get('closed', False)),
            'closed_departure': int(day_vals.get(
                'closed_departure',
                False)),
            'closed_arrival': int(day_vals.get(
                'closed_arrival',
                False)),
            'wpushed': True,
        }
        if room_type_restr:
            room_type_restr.with_context({
                'wubook_action': False,
            }).write(vals)
        else:
            vals.update({
                'restriction_id': restriction_plan_id,
                'room_type_id': room_type_id,
                'date_start': date_str,
                'date_end': date_str,
                'applied_on': '0_room_type',
            })
            room_type_restr_item_obj.with_context({
                'wubook_action': False,
            }).create(vals)

    @api.model
    def _generate_room_values(self, dfrom, dto, values, set_max_avail=False):
        room_type_restr_obj = self.env['hotel.room.type.restriction']
        hotel_room_type_obj = self.env['hotel.room.type']
        def_restr_plan = room_type_restr_obj.search([('wpid', '=', '0')])
        _logger.info("==== ROOM VALUES (%s -- %s)", dfrom, dto)
        _logger.info(values)
        for k_rid, v_rid in values.iteritems():
            room_type = hotel_room_type_obj.search([
                ('wrid', '=', k_rid)
            ], limit=1)
            if room_type:
                date_dt = date_utils.get_datetime(
                    dfrom,
                    dtformat=DEFAULT_WUBOOK_DATE_FORMAT)
                for day_vals in v_rid:
                    date_str = date_dt.strftime(DEFAULT_SERVER_DATE_FORMAT)
                    self._get_room_values_availability(
                        room_type.id,
                        date_str,
                        day_vals,
                        set_max_avail)
                    if def_restr_plan:
                        self._get_room_values_restrictions(
                            def_restr_plan.id,
                            room_type.id,
                            date_str,
                            day_vals)
                    date_dt = date_dt + timedelta(days=1)
        return True

    @api.model
    def _generate_booking_vals(self, broom, checkin_str, checkout_str,
                               is_cancellation, channel_info, wstatus, crcode,
                               rcode, room_type, split_booking, dates_checkin,
                               dates_checkout, book):
        # Generate Reservation Day Lines
        reservation_line_ids = []
        tprice = 0.0
        for brday in broom['roomdays']:
            wndate = date_utils.get_datetime(
                brday['day'],
                dtformat=DEFAULT_WUBOOK_DATE_FORMAT
            ).replace(tzinfo=pytz.utc)
            if date_utils.date_in(wndate,
                                  dates_checkin[0],
                                  dates_checkout[0] - timedelta(days=1),
                                  hours=False) == 0:
                reservation_line_ids.append((0, False, {
                    'date': wndate.strftime(
                        DEFAULT_SERVER_DATE_FORMAT),
                    'price': brday['price']
                }))
                tprice += brday['price']
        persons = room_type.wcapacity
        if 'ancillary' in broom and 'guests' in broom['ancillary']:
            persons = broom['ancillary']['guests']

        vals = {
            'channel_reservation_id': rcode,
            'ota_id': channel_info and channel_info.id,
            'ota_reservation_id': crcode,
            'channel_raw_data': json.dumps(book),
            'wstatus': wstatus,
            'wmodified': book['was_modified'],
            'odoo_id': [0, False, {
                'checkin': checkin_str,
                'checkout': checkout_str,
                'adults': persons,
                'children': book['children'],
                'reservation_line_ids': reservation_line_ids,
                'price_unit': tprice,
                'to_assign': True,
                'to_read': True,
                'state': is_cancellation and 'cancelled' or 'draft',
                'room_type_id': room_type.id,
                'splitted': split_booking,
            }],
        }
        _logger.info("===== CONTRUCT RESERV")
        _logger.info(vals)
        return vals

    @api.model
    def _generate_partner_vals(self, book):
        country_id = self.env['res.country'].search([
            ('code', '=', str(book['customer_country']))
        ], limit=1)
        # lang = self.env['res.lang'].search([('code', '=', book['customer_language_iso'])], limit=1)
        return {
            'name': "%s, %s" %
                    (book['customer_surname'], book['customer_name']),
            'country_id': country_id and country_id.id,
            'city': book['customer_city'],
            'phone': book['customer_phone'],
            'zip': book['customer_zip'],
            'street': book['customer_address'],
            'email': book['customer_mail'],
            'unconfirmed': True,
            # 'lang': lang and lang.id,
        }

    # FIXME: Super big method!!! O_o
    @api.model
    def _generate_reservations(self, bookings):
        _logger.info("=== BOOKINGS FROM WUBOOK")
        _logger.info(bookings)
        default_arrival_hour = self.env['ir.default'].sudo().get(
            'res.config.settings', 'default_arrival_hour')
        default_departure_hour = self.env['ir.default'].sudo().get(
            'res.config.settings', 'default_departure_hour')

        # Get user timezone
        tz_hotel = self.env['ir.default'].sudo().get(
            'res.config.settings', 'tz_hotel')
        res_partner_obj = self.env['res.partner']
        channel_reserv_obj = self.env['channel.hotel.reservation']
        hotel_reserv_obj = self.env['hotel.reservation']
        hotel_folio_obj = self.env['hotel.folio']
        channel_room_type_obj = self.env['channel.hotel.room.type']
        hotel_room_type_obj = self.env['hotel.room.type']
        # Space for store some data for construct folios
        processed_rids = []
        failed_reservations = []
        checkin_utc_dt = False
        checkout_utc_dt = False
        split_booking = False
        for book in bookings:   # This create a new folio
            splitted_map = {}
            is_cancellation = book['status'] in WUBOOK_STATUS_BAD
            bstatus = str(book['status'])
            rcode = str(book['reservation_code'])
            crcode = str(book['channel_reservation_code']) \
                if book['channel_reservation_code'] else 'undefined'

            # Can't process failed reservations
            #  (for example set a invalid new reservation and receive in
            # the same transaction an cancellation)
            if crcode in failed_reservations:
                self.create_issue(
                    'reservation',
                    "Can't process a reservation that previusly failed!",
                    '', channel_object_id=book['reservation_code'])
                continue

            # Get dates for the reservation (GMT->UTC)
            arr_hour = default_arrival_hour if book['arrival_hour'] == "--" \
                else book['arrival_hour']
            checkin = "%s %s" % (book['date_arrival'], arr_hour)
            checkin_dt = date_utils.get_datetime(
                checkin,
                dtformat=DEFAULT_WUBOOK_DATETIME_FORMAT,
                stz=tz_hotel)
            checkin_utc_dt = date_utils.dt_as_timezone(checkin_dt, 'UTC')
            checkin = checkin_utc_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

            checkout = "%s %s" % (book['date_departure'],
                                  default_departure_hour)
            checkout_dt = date_utils.get_datetime(
                checkout,
                dtformat=DEFAULT_WUBOOK_DATETIME_FORMAT,
                stz=tz_hotel)
            checkout_utc_dt = date_utils.dt_as_timezone(checkout_dt, 'UTC')
            checkout = checkout_utc_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

            # Search Folio. If exists.
            folio_id = False
            if crcode != 'undefined':
                reserv_folio = channel_reserv_obj.search([
                    ('ota_reservation_id', '=', crcode)
                ], limit=1)
                if reserv_folio:
                    folio_id = reserv_folio.odoo_id.folio_id
            else:
                reserv_folio = channel_reserv_obj.search([
                    ('channel_reservation_id', '=', rcode)
                ], limit=1)
                if reserv_folio:
                    folio_id = reserv_folio.odoo_id.folio_id

            # Need update reservations?
            sreservs = channel_reserv_obj.search([('channel_reservation_id', '=', rcode)])
            reservs = folio_id.room_lines if folio_id else sreservs.mapped(lambda x: x.odoo_id)
            reservs_processed = False
            if any(reservs):
                folio_id = reservs[0].folio_id
                for reserv in reservs:
                    if reserv.channel_reservation_id == rcode:
                        binding_id = reserv.channel_bind_ids[0]
                        binding_id.write({
                            'channel_raw_data': json.dumps(book),
                            'wstatus': str(book['status']),
                            'wstatus_reason': book.get('status_reason', ''),
                        })
                        reserv.with_context({'wubook_action': False}).write({
                            'to_read': True,
                            'to_assign': True,
                            'price_unit': book['amount'],
                            'customer_notes': book['customer_notes'],
                        })
                        if reserv.partner_id.unconfirmed:
                            reserv.partner_id.write(
                                self._generate_partner_vals(book)
                            )
                        reservs_processed = True
                        if is_cancellation:
                            reserv.with_context({
                                'wubook_action': False}).action_cancel()
                        elif reserv.state == 'cancelled':
                            reserv.with_context({
                                'wubook_action': False,
                            }).write({
                                'discount': 0.0,
                                'state': 'confirm',
                            })

            # Do Nothing if already processed 'wrid'
            if reservs_processed:
                processed_rids.append(rcode)
                continue

            # Search Customer
            customer_mail = book.get('customer_mail', False)
            partner_id = False
            if customer_mail:
                partner_id = res_partner_obj.search([
                    ('email', '=', customer_mail)
                ], limit=1)
            if not partner_id:
                partner_id = res_partner_obj.create(self._generate_partner_vals(book))

            # Search Wubook Channel Info
            channel_info = self.env['hotel.channel.connector.ota.info'].search(
                [('ota_id', '=', str(book['id_channel']))], limit=1)

            reservations = []
            used_rooms = []
            # Iterate booked rooms
            for broom in book['booked_rooms']:
                room_type = channel_room_type_obj.search([
                    ('channel_room_id', '=', broom['room_id'])
                ], limit=1)
                if not room_type:
                    self.create_issue(
                        'reservation',
                        "Can't found any room type associated to '%s' \
                                                in this hotel" % book['rooms'],
                        '', channel_object_id=book['reservation_code'])
                    failed_reservations.append(crcode)
                    continue

                dates_checkin = [checkin_utc_dt, False]
                dates_checkout = [checkout_utc_dt, False]
                split_booking = False
                split_booking_parent = False
                # This perhaps create splitted reservation
                while dates_checkin[0]:
                    checkin_str = dates_checkin[0].strftime(
                        DEFAULT_SERVER_DATETIME_FORMAT)
                    checkout_str = dates_checkout[0].strftime(
                        DEFAULT_SERVER_DATETIME_FORMAT)
                    vals = self._generate_booking_vals(
                        broom,
                        checkin_str,
                        checkout_str,
                        is_cancellation,
                        channel_info,
                        bstatus,
                        crcode,
                        rcode,
                        room_type.odoo_id,
                        split_booking,
                        dates_checkin,
                        dates_checkout,
                        book,
                    )
                    if vals['price_unit'] != book['amount']:
                        self.create_issue(
                            'reservation',
                            "Invalid reservation total price! %.2f != %.2f" % (vals['price_unit'], book['amount']),
                            '', channel_object_id=book['reservation_code'])

                    free_rooms = room_type.odoo_id.check_availability_room(
                        checkin_str,
                        checkout_str,
                        room_type_id=room_type.odoo_id.id,
                        notthis=used_rooms)
                    if any(free_rooms):
                        vals.update({
                            'product_id': free_rooms[0].product_id.id,
                            'name': free_rooms[0].name,
                        })
                        reservations.append((0, False, vals))
                        used_rooms.append(free_rooms[0].id)

                        if split_booking:
                            if not split_booking_parent:
                                split_booking_parent = len(reservations)
                            else:
                                splitted_map.setdefault(
                                    split_booking_parent,
                                    []).append(len(reservations))
                        dates_checkin = [dates_checkin[1], False]
                        dates_checkout = [dates_checkout[1], False]
                    else:
                        date_diff = (dates_checkout[0].replace(
                            hour=0, minute=0, second=0,
                            microsecond=0) -
                                     dates_checkin[0].replace(
                                         hour=0, minute=0, second=0,
                                         microsecond=0)).days
                        if date_diff <= 0:
                            if split_booking:
                                if split_booking_parent:
                                    del reservations[split_booking_parent-1:]
                                    if split_booking_parent in splitted_map:
                                        del splitted_map[split_booking_parent]
                            # Can't found space for reservation
                            vals = self._generate_booking_vals(
                                broom,
                                checkin_utc_dt,
                                checkout_utc_dt,
                                is_cancellation,
                                channel_info,
                                bstatus,
                                crcode,
                                rcode,
                                room_type.odoo_id,
                                False,
                                (checkin_utc_dt, False),
                                (checkout_utc_dt, False),
                                book,
                            )
                            vals.update({
                                'product_id':
                                    room_type.odoo_id.room_ids[0].product_id.id,
                                'name': room_type.odoo_id.name,
                                'overbooking': True,
                            })
                            reservations.append((0, False, vals))
                            self.create_issue(
                                'reservation',
                                "Reservation imported with overbooking state",
                                '', channel_object_id=rcode)
                            dates_checkin = [False, False]
                            dates_checkout = [False, False]
                            split_booking = False
                        else:
                            split_booking = True
                            dates_checkin = [
                                dates_checkin[0],
                                dates_checkin[0] + timedelta(days=date_diff-1)
                            ]
                            dates_checkout = [
                                dates_checkout[0] - timedelta(days=1),
                                checkout_utc_dt
                            ]

            if split_booking:
                self.create_issue(
                    'reservation',
                    "Reservation Splitted",
                    '', channel_object_id=rcode)

            # Create Folio
            if not any(failed_reservations) and any(reservations):
                try:
                    # TODO: Improve 'addons_list' & discounts
                    addons = str(book['addons_list']) if any(book['addons_list']) else ''
                    discounts = book.get('discount', '')
                    vals = {
                        'room_lines': reservations,
                        'wcustomer_notes': "%s\nADDONS:\n%s\nDISCOUNT:\n%s" % (
                            book['customer_notes'], addons, discounts),
                        'channel_type': 'web',
                    }
                    _logger.info("=== FOLIO CREATE")
                    _logger.info(reservations)
                    if folio_id:
                        folio_id.with_context({
                            'wubook_action': False}).write(vals)
                    else:
                        vals.update({
                            'partner_id': partner_id.id,
                            'wseed': book['sessionSeed']
                        })
                        folio_id = hotel_folio_obj.with_context({
                            'wubook_action': False}).create(vals)

                    # Update Reservation Spitted Parents
                    sorted_rlines = folio_id.room_lines.sorted(key='id')
                    for k_pid, v_pid in splitted_map.iteritems():
                        preserv = sorted_rlines[k_pid-1]
                        for pid in v_pid:
                            creserv = sorted_rlines[pid-1]
                            creserv.parent_reservation = preserv.id

                    processed_rids.append(rcode)
                except ChannelConnectorError as err:
                    self.create_issue(
                        'reservation',
                        err.data['message'],
                        '', channel_object_id=rcode)
                    failed_reservations.append(crcode)
        return (processed_rids, any(failed_reservations),
                checkin_utc_dt, checkout_utc_dt)

    @api.model
    def _generate_pricelists(self, price_plans):
        product_listprice_obj = self.env['product.pricelist']
        count = 0
        for plan in price_plans:
            if 'vpid' in plan:
                continue    # Ignore Virtual Plans

            vals = {
                'name': plan['name'],
                'is_daily_plan': plan['daily'] == 1,
            }
            plan_id = product_listprice_obj.search([
                ('wpid', '=', str(plan['id']))
            ], limit=1)
            if not plan_id:
                vals.update({
                    'wpid': str(plan['id']),
                })
                product_listprice_obj.with_context({
                    'wubook_action': False}).create(vals)
            else:
                plan_id.with_context({'wubook_action': False}).write(vals)
            count = count + 1
        return count

    @api.model
    def _generate_pricelist_items(self, channel_plan_id, date_from, date_to, plan_prices):
        hotel_room_type_obj = self.env['hotel.room.type']
        pricelist = self.env['product.pricelist'].search([
            ('wpid', '=', channel_plan_id)
        ], limit=1)
        if pricelist:
            pricelist_item_obj = self.env['product.pricelist.item']
            dfrom_dt = date_utils.get_datetime(date_from)
            dto_dt = date_utils.get_datetime(date_to)
            days_diff = date_utils.date_diff(dfrom_dt, dto_dt, hours=False) + 1
            for i in range(0, days_diff):
                ndate_dt = dfrom_dt + timedelta(days=i)
                for k_rid, v_rid in plan_prices.iteritems():
                    room_type = hotel_room_type_obj.search([
                        ('wrid', '=', k_rid)
                    ], limit=1)
                    if room_type:
                        pricelist_item = pricelist_item_obj.search([
                            ('pricelist_id', '=', pricelist.id),
                            ('date_start', '=', ndate_dt.strftime(
                                DEFAULT_SERVER_DATE_FORMAT)),
                            ('date_end', '=', ndate_dt.strftime(
                                DEFAULT_SERVER_DATE_FORMAT)),
                            ('compute_price', '=', 'fixed'),
                            ('applied_on', '=', '1_product'),
                            ('product_tmpl_id', '=', room_type.product_id.product_tmpl_id.id)
                        ], limit=1)
                        vals = {
                            'fixed_price': plan_prices[k_rid][i],
                            'wpushed': True,
                        }
                        if pricelist_item:
                            pricelist_item.with_context({
                                'wubook_action': False}).write(vals)
                        else:
                            vals.update({
                                'pricelist_id': pricelist.id,
                                'date_start': ndate_dt.strftime(
                                    DEFAULT_SERVER_DATE_FORMAT),
                                'date_end': ndate_dt.strftime(
                                    DEFAULT_SERVER_DATE_FORMAT),
                                'compute_price': 'fixed',
                                'applied_on': '1_product',
                                'product_tmpl_id': room_type.product_id.product_tmpl_id.id
                            })
                            pricelist_item_obj.with_context({
                                'wubook_action': False}).create(vals)
        return True

    @api.model
    def _generate_restrictions(self, restriction_plans):
        restriction_obj = self.env['hotel.room.type.restriction']
        count = 0
        for plan in restriction_plans:
            vals = {
                'name': plan['name'],
            }
            plan_id = restriction_obj.search([
                ('wpid', '=', str(plan['id']))
            ], limit=1)
            if not plan_id:
                vals.update({
                    'wpid': str(plan['id']),
                })
                restriction_obj.with_context({
                    'wubook_action': False,
                    'rules': plan.get('rules'),
                }).create(vals)
            else:
                plan_id.with_context({'wubook_action': False}).write(vals)
            count = count + 1
        return count

    @api.model
    def _generate_restriction_items(self, plan_restrictions):
        hotel_room_type_obj = self.env['hotel.room.type']
        reserv_restriction_obj = self.env['hotel.room.type.restriction']
        restriction_item_obj = self.env['hotel.room.type.restriction.item']
        _logger.info("===== RESTRICTIONS")
        _logger.info(plan_restrictions)
        for k_rpid, v_rpid in plan_restrictions.iteritems():
            restriction_id = reserv_restriction_obj.search([
                ('wpid', '=', k_rpid)
            ], limit=1)
            if restriction_id:
                for k_rid, v_rid in v_rpid.iteritems():
                    room_type = hotel_room_type_obj.search([
                        ('wrid', '=', k_rid)
                    ], limit=1)
                    if room_type:
                        for item in v_rid:
                            date_dt = date_utils.get_datetime(
                                item['date'],
                                dtformat=DEFAULT_WUBOOK_DATE_FORMAT)
                            restriction_item = restriction_item_obj.search([
                                ('restriction_id', '=', restriction_id.id),
                                ('date_start', '=', date_dt.strftime(
                                    DEFAULT_SERVER_DATE_FORMAT)),
                                ('date_end', '=', date_dt.strftime(
                                    DEFAULT_SERVER_DATE_FORMAT)),
                                ('applied_on', '=', '0_room_type'),
                                ('room_type_id', '=', room_type.id)
                            ], limit=1)
                            vals = {
                                'closed_arrival': item['closed_arrival'],
                                'closed': item['closed'],
                                'min_stay': item['min_stay'],
                                'closed_departure': item['closed_departure'],
                                'max_stay': item['max_stay'],
                                'max_stay_arrival': item['max_stay_arrival'],
                                'min_stay_arrival': item['min_stay_arrival'],
                                'wpushed': True,
                            }
                            if restriction_item:
                                restriction_item.with_context({
                                    'wubook_action': False}).write(vals)
                            else:
                                vals.update({
                                    'restriction_id': restriction_id.id,
                                    'date_start': date_dt.strftime(
                                        DEFAULT_SERVER_DATE_FORMAT),
                                    'date_end': date_dt.strftime(
                                        DEFAULT_SERVER_DATE_FORMAT),
                                    'applied_on': '0_room_type',
                                    'room_type_id': room_type.id
                                })
                                restriction_item_obj.with_context({
                                    'wubook_action': False}).create(vals)

        return True

    @api.model
    def fetch_booking(self, channel_reservation_id):
        try:
            results = self.backend_adapter.fetch_booking(channel_reservation_id)
            processed_rids, errors, checkin_utc_dt, checkout_utc_dt = \
                self.generate_reservations(results)
            if any(processed_rids):
                self.backend_adapter.mark_bookings(list(set(processed_rids)))

            # Update Odoo availability (don't wait for wubook)
            if checkin_utc_dt and checkout_utc_dt:
                self.backend_adapter.fetch_rooms_values(
                    checkin_utc_dt.strftime(DEFAULT_SERVER_DATE_FORMAT),
                    checkout_utc_dt.strftime(DEFAULT_SERVER_DATE_FORMAT))
        except ChannelConnectorError as err:
            self.create_issue(
                'reservation',
                _("Can't process reservations from wubook"),
                err.data['message'], channel_object_id=channel_reservation_id)
            return False
        return True

    @api.model
    def import_pricing_plans(self):
        try:
            results = self.backend_adapter.get_pricing_plans()
            count = self._generate_pricelists(results)
        except ChannelConnectorError as err:
            self.create_issue(
                'plan',
                _("Can't get pricing plans from wubook"),
                err.data['message'])
            return 0
        return count

    @api.model
    def fetch_plan_prices(self, channel_plan_id, date_from, date_to, rooms=None):
        try:
            results = self.backend_adapter.fetch_plan_prices(
                channel_plan_id,
                date_from,
                date_to,
                rooms)
            self._generate_pricelist_items(channel_plan_id, date_from, date_to, results)
        except ChannelConnectorError as err:
            self.create_issue(
                'plan',
                _("Can't fetch plan prices from wubook"),
                err.data['message'])
            return False
        return True

    @api.model
    def fetch_all_plan_prices(self, date_from, date_to, rooms=None):
        no_errors = True
        channel_plan_ids = self.env['product.pricelist'].search([
            ('wpid', '!=', False), ('wpid', '!=', '')
        ]).mapped('wpid')
        if any(channel_plan_ids):
            try:
                for channel_plan_id in channel_plan_ids:
                    results = self.backend_adapter.fetch_plan_prices(
                        channel_plan_id,
                        date_from,
                        date_to,
                        rooms)
                    self._generate_pricelist_items(channel_plan_id, date_from, date_to, results)
            except ChannelConnectorError as err:
                self.create_issue(
                    'plan',
                    "Can't fetch all plan prices from wubook!",
                    err.data['message'],
                    channel_object_id=channel_plan_id, dfrom=date_from, dto=date_to)
                return False
        return no_errors

    @api.model
    def import_restriction_plans(self):
        try:
            results = self.backend_adapter.rplan_rplans()
            count = self._generate_restrictions(results)
        except ChannelConnectorError as err:
            self.create_issue(
                'rplan',
                _("Can't fetch restriction plans from wubook"),
                err.data['message'])
            return 0
        return count

    @api.model
    def fetch_rplan_restrictions(self, date_from, date_to, channel_restriction_plan_id=False):
        try:
            results = self.backend_adapter.wired_rplan_get_rplan_values(
                date_from,
                date_to,
                int(channel_restriction_plan_id))
            if any(results):
                self._generate_restriction_items(results)
        except ChannelConnectorError as err:
            self.create_issue(
                'rplan',
                _("Can't fetch plan restrictions from wubook"),
                err.data['message'],
                channel_object_id=channel_restriction_plan_id,
                dfrom=date_from, dto=date_to)
            return False
        return True

class BatchImporter(AbstractComponent):
    """ The role of a BatchImporter is to search for a list of
    items to import, then it can either import them directly or delay
    the import of each item separately.
    """

    _name = 'channel.batch.importer'
    _inherit = ['base.importer', 'base.hotel.channel.connector']
    _usage = 'batch.importer'

    def _import_record(self, external_id):
        """ Import a record directly or delay the import of the record.

        Method to implement in sub-classes.
        """
        raise NotImplementedError

class DirectBatchImporter(AbstractComponent):
    """ Import the records directly, without delaying the jobs. """

    _name = 'channel.direct.batch.importer'
    _inherit = 'channel.batch.importer'

    def _import_record(self, external_id):
        """ Import the record directly """
        self.model.import_record(self.backend_record, external_id)
