# -*- coding: utf-8 -*-
# Copyright 2018  Alexandre Díaz
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Hotel Management',
    'version': '0.07',
    'author': 'Odoo Community Association (OCA),\
    Darío Lodeiros,\
    Jose Luis Algara,\
    Alexandre Díaz',
    'images': [],
    'category': 'Generic Modules/Hotel Management',
    'website': '',
    'depends': [
        'sale_stock',
        'account_payment_return',
    ],
    'license': "",
    'demo': ['data/hotel_data.xml'],
    'data': [
        'security/hotel_security.xml',
        'security/ir.model.access.csv',
        'wizard/massive_changes.xml',
        'wizard/split_reservation.xml',
        'wizard/duplicate_reservation.xml',
        'views/res_config.xml',
        'data/menus.xml',
        'views/inherit_account_payment_views.xml',
        'views/inherit_account_invoice_views.xml',
        'wizard/hotel_wizard.xml',
        'wizard/checkinwizard.xml',
        'wizard/massive_price_reservation_days.xml',
        'wizard/folio_make_invoice_advance_views.xml',
        'views/hotel_sequence.xml',
        'views/hotel_report.xml',
        'views/report_hotel_management.xml',
        'views/currency_exchange.xml',
        'views/hotel_floor.xml',
        'views/hotel_folio.xml',
        'views/inherit_res_partner.xml',
        # 'views/hotel_service_type.xml',
        # 'views/hotel_service_line.xml',
        'views/hotel_room_type.xml',
        'views/hotel_room.xml',
        'views/hotel_room_type_class.xml',
        # 'views/hotel_service.xml',
        'views/inherit_product_product.xml',
        'views/hotel_room_amenities_type.xml',
        'views/hotel_room_amenities.xml',
        'views/hotel_room_type_restriction_views.xml',
        'views/hotel_room_type_restriction_item_views.xml',
        'views/hotel_reservation.xml',
        # 'views/room_type_views.xml',
        'views/cardex.xml',
        'views/hotel_room_type_availability.xml',
        # 'views/hotel_dashboard.xml',
        'data/cron_jobs.xml',
        'data/records.xml',
        'data/email_template_cancel.xml',
        'data/email_template_reserv.xml',
        'data/email_template_exit.xml',
    ],
    'css': ['static/src/css/room_kanban.css'],
    'auto_install': False,
    'installable': True
}
