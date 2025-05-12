from datetime import timedelta

# Request paremeters (body and query) constructore
def _5_sale_entries_extraction_request_params(serializer, gregorian_now):
    pass
def _h_extract_numbers_request_params(serializer, gregorian_now):
    pass

def _5_call_logs_list_request_params(serializer, gregorian_now):
    date_gregorian = gregorian_now.date()

    startCallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')
    endCallDate = (date_gregorian).strftime('%Y-%m-%d')
    params_5_call_logs = {
        'report': serializer.validated_data.get('report', 1),
        'filter': serializer.validated_data.get('filter', 1),
        'callLocations': serializer.validated_data.get('callLocations', 'sale'),
        'startCallDate': serializer.validated_data.get('startCallDate', f"{startCallDate} 00:00:00" ),
        'endCallDate': serializer.validated_data.get('endCallDate', f"{endCallDate} 23:59:59")
    }

    return params_5_call_logs, 'startCallDate', 'endCallDate'

def _h_call_log_index_request_params(serializer, gregorian_now):
    date_gregorian = gregorian_now.date()

    startCallDate = (date_gregorian - timedelta(days=1)).strftime('%Y-%m-%d')
    endCallDate = (date_gregorian).strftime('%Y-%m-%d')
    params_h_call_logs = {
        'export_data': serializer.validated_data.get('export_data', 1),
        'filter': serializer.validated_data.get('filter', 1),
        'start_call_from': serializer.validated_data.get('start_call_from', f"{startCallDate} 00:00:00" ),
        'start_call_to': serializer.validated_data.get('start_call_to', f"{endCallDate} 23:59:59"),
        'location': serializer.validated_data.get('location', 'sale')
    }

    return params_h_call_logs, 'start_call_from', 'start_call_to'

def _5_factors_list_request_params(serializer, gregorian_now):
    pass
def _h_factor_index_request_params(serializer, gregorian_now):
    pass
