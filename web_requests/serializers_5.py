from rest_framework import serializers

# 5040

# Extraction
class EntriesExtraction_5(serializers.Serializer):
        
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

class FactorsList(serializers.Serializer):
    report = serializers.IntegerField(required=False)
    filter = serializers.IntegerField(required=False)
    startInvoiceDate = serializers.CharField(required=False)
    endInvoiceDate = serializers.CharField(required=False)
