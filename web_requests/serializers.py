from rest_framework import serializers

class SendCodeSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    type = serializers.CharField()

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    code = serializers.CharField()

class cm10Serializer(serializers.Serializer):
    export_data = serializers.CharField(default="1")
    call_type = serializers.ListField(child=serializers.CharField(), default=["1"])
    start_at = serializers.CharField(required=False)
    end_at = serializers.CharField(required=False)