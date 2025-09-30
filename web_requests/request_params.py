from datetime import timedelta

# Request paremeters (body and query) constructore
def _5_sale_entries_extraction_request_params(serializer, gregorian_now):
    pass
def _h_extract_numbers_request_params(serializer, gregorian_now):
    pass


def _5_call_logs_list_request_params(serializer, gregorian_now):

    date_gregorian = gregorian_now.date()
    flag_CallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')

    params = {
        'report': serializer.validated_data.get('report', 1),
        'filter': serializer.validated_data.get('filter', 1),
        'startCallDate': serializer.validated_data.get('startCallDate', f"{flag_CallDate} 00:00:00"),
        'endCallDate': serializer.validated_data.get('endCallDate', f"{flag_CallDate} 23:59:59")
    }
    if 'callLocations' in serializer.validated_data:
        params['callLocations'] = serializer.validated_data.get('callLocations', 'Sale')

    return params, 'startCallDate', 'endCallDate'

def _h_call_log_index_request_params(serializer, gregorian_now):

    date_gregorian = gregorian_now.date()
    flag_CallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')

    params = {
        'export_data': serializer.validated_data.get('export_data', 1),
        'start_call_from': serializer.validated_data.get('start_call_from', f"{flag_CallDate} 00:00:00"),
        'start_call_to': serializer.validated_data.get('start_call_to', f"{flag_CallDate} 23:59:59"),
    }
    if 'location' in serializer.validated_data:
        params['location'] = serializer.validated_data.get('location', 'sale')
        
    return params, 'start_call_from', 'start_call_to'


def _5_factors_list_request_params(serializer, gregorian_now):
    date_gregorian = gregorian_now.date()
    flag_CallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')

    start_dt_prm_name = ""
    end_dt_prm_name = ""

    params = {
        'report': serializer.validated_data.get('report', 1),
        'filter': serializer.validated_data.get('filter', 1),
    }

    if 'startInvoiceDate' in serializer.validated_data:
        start_dt_prm_name = 'startInvoiceDate'
        params['startInvoiceDate'] = serializer.validated_data.get('startInvoiceDate', f"{flag_CallDate} 00:00:00")
    if 'endInvoiceDate' in serializer.validated_data:
        end_dt_prm_name = 'endInvoiceDate'
        params['endInvoiceDate'] = serializer.validated_data.get('endInvoiceDate', f"{flag_CallDate} 23:59:59")

    if 'startPayAcceptDate' in serializer.validated_data:
        if not start_dt_prm_name:
            start_dt_prm_name = 'startPayAcceptDate'
        params['startPayAcceptDate'] = serializer.validated_data.get('startPayAcceptDate', f"{flag_CallDate} 00:00:00")
    if 'endPayAcceptDate' in serializer.validated_data:
        if not end_dt_prm_name:
            end_dt_prm_name = 'endPayAcceptDate'
        params['endPayAcceptDate'] = serializer.validated_data.get('endPayAcceptDate', f"{flag_CallDate} 23:59:59")

    if 'payStatus' in serializer.validated_data:
        params['payStatus'] = serializer.validated_data.get('payStatus', "")

    return params, start_dt_prm_name, end_dt_prm_name

def _5_v1_factor_extraction_params(serializer, gregorian_now):
    date_gregorian = gregorian_now.date()
    flag_CallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')

    start_dt_prm_name = ""
    end_dt_prm_name = ""

    params = {
        'report': serializer.validated_data.get('report', 1),
        'filter': serializer.validated_data.get('filter', 1),
    }

    if 'startInvoiceDate' in serializer.validated_data:
        start_dt_prm_name = 'startInvoiceDate'
        params['startInvoiceDate'] = serializer.validated_data.get('startInvoiceDate', f"{flag_CallDate} 00:00:00")
    if 'endInvoiceDate' in serializer.validated_data:
        end_dt_prm_name = 'endInvoiceDate'
        params['endInvoiceDate'] = serializer.validated_data.get('endInvoiceDate', f"{flag_CallDate} 23:59:59")

    if 'startPayAcceptDate' in serializer.validated_data:
        if not start_dt_prm_name:
            start_dt_prm_name = 'startPayAcceptDate'
        params['startPayAcceptDate'] = serializer.validated_data.get('startPayAcceptDate', f"{flag_CallDate} 00:00:00")
    if 'endPayAcceptDate' in serializer.validated_data:
        if not end_dt_prm_name:
            end_dt_prm_name = 'endPayAcceptDate'
        params['endPayAcceptDate'] = serializer.validated_data.get('endPayAcceptDate', f"{flag_CallDate} 23:59:59")

    if 'payStatus' in serializer.validated_data:
        params['payStatus'] = serializer.validated_data.get('payStatus', "")

    esp_opt = {
        'datesep': '-'
    }

    return params, start_dt_prm_name, end_dt_prm_name, esp_opt

def _5_v1_extraction(serializer, gregorian_now):
    date_gregorian = gregorian_now.date()
    flag_CallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')

    params = {
        'references': serializer.validated_data.get('references', []),
        'containDeletedEntries': serializer.validated_data.get('containDeletedEntries', False),
        'startEntryDate': serializer.validated_data.get('startEntryDate', f"{flag_CallDate} 00:00:00"),
        'endEntryDate': serializer.validated_data.get('endEntryDate', f"{flag_CallDate} 23:59:59"),
        'agencies': serializer.validated_data.get('agencies', []),
        'callStatuses': serializer.validated_data.get('callStatuses', []),
        'containDeletedEntries': serializer.validated_data.get('containDeletedEntries', False),
        'factorSerial': serializer.validated_data.get('factorSerial', ""),
        'factorStatuses': serializer.validated_data.get('factorStatuses', []),
        'justDeletedEntries': serializer.validated_data.get('justDeletedEntries', False),
        'maxCallNumber': serializer.validated_data.get('maxCallNumber', 0),
        'maxSuccessCallNumber': serializer.validated_data.get('maxSuccessCallNumber', 0),
        'minCallNumber': serializer.validated_data.get('minCallNumber', 0),
        'minSuccessCallNumber': serializer.validated_data.get('minSuccessCallNumber', 0),
        'mobile': serializer.validated_data.get('mobile', ""),
        'numberStatuses': serializer.validated_data.get('numberStatuses', []),
        'products': serializer.validated_data.get('products', []),
        'withoutFactorEntries': serializer.validated_data.get('withoutFactorEntries', False),
    }


    return params, "startEntryDate", "endEntryDate"

##############################
##############################


def _h_factor_index_request_params(serializer, gregorian_now):

    date_gregorian = gregorian_now.date()
    flag_CallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')

    start_dt_prm_name = ""
    end_dt_prm_name = ""

    params = {
        'export_data': serializer.validated_data.get('export_data', 1),
    }

    if 'start_created_at' in serializer.validated_data:
        start_dt_prm_name = 'start_created_at'
        params['start_created_at'] = serializer.validated_data.get('start_created_at', f"{flag_CallDate} 00:00:00")
    if 'end_created_at' in serializer.validated_data:
        end_dt_prm_name = 'end_created_at'
        params['end_created_at'] = serializer.validated_data.get('end_created_at', f"{flag_CallDate} 23:59:59")

    if 'start_accept_action_date' in serializer.validated_data:
        if not start_dt_prm_name:
            start_dt_prm_name = 'start_accept_action_date'
        params['start_accept_action_date'] = serializer.validated_data.get('start_accept_action_date', f"{flag_CallDate} 00:00:00")
    if 'end_accept_action_date' in serializer.validated_data:
        if not end_dt_prm_name:
            end_dt_prm_name = 'end_accept_action_date'
        params['end_accept_action_date'] = serializer.validated_data.get('end_accept_action_date', f"{flag_CallDate} 23:59:59")

    if 'status' in serializer.validated_data:
        params['status'] = serializer.validated_data.get('status', "")

    if 'receipt_status' in serializer.validated_data:
        params['receipt_status'] = serializer.validated_data.get('receipt_status', "")

    return params, start_dt_prm_name, end_dt_prm_name



def _h_accounting_call_log_index(serializer, gregorian_now):

    date_gregorian = gregorian_now.date()
    flag_CallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')

    params = {
        'export_data': serializer.validated_data.get('export_data', 1),
        'call_type[]': serializer.validated_data.get('call_type', ""),
        'start_at': serializer.validated_data.get('start_at', f"{flag_CallDate} 00:00:00"),
        'end_at': serializer.validated_data.get('end_at', f"{flag_CallDate} 23:59:59"),
    }
    return params, 'start_at', 'end_at'



def _h_reservation_index(serializer, gregorian_now):

    date_gregorian = gregorian_now.date()
    flag_CallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')

    start_dt_prm_name = ""
    end_dt_prm_name = ""

    params = {
        'export_data': serializer.validated_data.get('export_data', 1),
    }
    if 'start_created_at' in serializer.validated_data:
        start_dt_prm_name = 'start_created_at'
        params['start_created_at'] = serializer.validated_data.get('start_created_at', f"{flag_CallDate} 00:00:00")
    if 'end_created_at' in serializer.validated_data:
        end_dt_prm_name = 'end_created_at'
        params['end_created_at'] = serializer.validated_data.get('end_created_at', f"{flag_CallDate} 23:59:59")

    if 'start_reserved_at' in serializer.validated_data:
        start_dt_prm_name = 'start_reserved_at'
        params['start_reserved_at'] = serializer.validated_data.get('start_reserved_at', f"{flag_CallDate} 00:00:00")
    if 'end_reserved_at' in serializer.validated_data:
        end_dt_prm_name = 'end_reserved_at'
        params['end_reserved_at'] = serializer.validated_data.get('end_reserved_at', f"{flag_CallDate} 23:59:59")

    return params, start_dt_prm_name, end_dt_prm_name

def _h_entryـextractـnumbersـnew(serializer, gregorian_now):

    date_gregorian = gregorian_now.date()
    flag_CallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')

    params = {
        'product_id': serializer.validated_data.get('product_id', 3),
        'reference': serializer.validated_data.get('reference', []),
        'entry_date_start': serializer.validated_data.get('entry_date_start', f"{flag_CallDate} 00:00:00"),
        'entry_date_end': serializer.validated_data.get('entry_date_end', f"{flag_CallDate} 23:59:59"),
    }

    if 'agency_id' in serializer.validated_data:
        params['agency_id'] = serializer.validated_data.get('agency_id', [])
    if 'category_ids' in serializer.validated_data:
        params['category_ids'] = serializer.validated_data.get('category_ids', [])
    if 'entry_status' in serializer.validated_data:
        params['entry_status'] = serializer.validated_data.get('entry_status', [])
    if 'entry_voided' in serializer.validated_data:
        params['entry_voided'] = serializer.validated_data.get('entry_voided', False)
    if 'factor_serial' in serializer.validated_data:
        params['factor_serial'] = serializer.validated_data.get('factor_serial', "")
    if 'factor_status' in serializer.validated_data:
        params['factor_status'] = serializer.validated_data.get('factor_status', [])
    if 'max_call_count' in serializer.validated_data:
        params['max_call_count'] = serializer.validated_data.get('max_call_count', "")
    if 'max_call_count_success' in serializer.validated_data:
        params['max_call_count_success'] = serializer.validated_data.get('max_call_count_success', "")
    if 'min_call_count' in serializer.validated_data:
        params['min_call_count'] = serializer.validated_data.get('min_call_count', "")
    if 'min_call_count_success' in serializer.validated_data:
        params['min_call_count_success'] = serializer.validated_data.get('min_call_count_success', "")
    if 'mobile' in serializer.validated_data:
        params['mobile'] = serializer.validated_data.get('mobile', "")
    if 'type' in serializer.validated_data:
        params['type'] = serializer.validated_data.get('type', "")

    esp_opt = {
        'datesep': '-'
    }

    """
    Legend:
    esp_opt: especific options
    datesep: date seperator
    """

    return params, 'entry_date_start', 'entry_date_end', esp_opt
