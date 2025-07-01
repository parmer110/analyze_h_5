from rest_framework import serializers

class AccountingCallLog(serializers.Serializer):
    export_data = serializers.CharField(required=False)
    call_type = serializers.ListField(child=serializers.CharField(), required=False)
    start_at = serializers.CharField(required=False)
    end_at = serializers.CharField(required=False)

# Extraction
class EntriesExtraction_f(serializers.Serializer):
        
    callStatuses = serializers.ListField(child=serializers.CharField(), required=False)
    containDeletedEntries = serializers.BooleanField(required=False)
    endEntryDate = serializers.DateTimeField(required=False)
    factorSerial = serializers.CharField(required=False, allow_blank=True)
    factorStatuses = serializers.ListField(child=serializers.CharField(), required=False)
    isTrusted = serializers.BooleanField(required=False)
    justDeletedEntries = serializers.BooleanField(required=False)
    maxCallNumber = serializers.CharField(required=False, allow_blank=True)
    maxSuccessCallNumber = serializers.CharField(required=False, allow_blank=True)
    minCallNumber = serializers.CharField(required=False, allow_blank=True)
    minSuccessCallNumber = serializers.CharField(required=False, allow_blank=True)
    mobile = serializers.CharField(required=False, allow_blank=True)
    numberStatuses = serializers.ListField(child=serializers.CharField(), required=False)
    products = serializers.ListField(child=serializers.CharField(), required=False)
    references = serializers.ListField(child=serializers.CharField(), required=False)
    startEntryDate = serializers.DateTimeField(required=False)
    withoutFactorEntries = serializers.BooleanField(required=False)
