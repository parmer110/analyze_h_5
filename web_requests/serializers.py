from rest_framework import serializers

class SendCodeSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    type = serializers.CharField()

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(required=False, default=serializers.empty)
    code = serializers.CharField()

class AccountingCallLog(serializers.Serializer):
    export_data = serializers.CharField(required=False)
    call_type = serializers.ListField(child=serializers.CharField(), required=False)
    start_at = serializers.CharField(required=False)
    end_at = serializers.CharField(required=False)
