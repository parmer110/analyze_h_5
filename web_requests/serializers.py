import jdatetime
import datetime
from rest_framework import serializers

class JalaliDateTimeField(serializers.Field):
    DEFAULT_FORMATS = [
        '%Y/%m/%d %H:%M:%S',  # Full format with seconds
        '%Y/%m/%d %H:%M',     # Without seconds
        '%Y/%m/%d',           # Date only
    ]

    def __init__(self, formats=None, default_time=None, *args, **kwargs):
        self.formats = formats or self.DEFAULT_FORMATS
        self.default_time = default_time or (0, 0, 0)
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        # 1. Parse as Jalali datetime
        for fmt in self.formats:
            try:
                parsed = jdatetime.datetime.strptime(data, fmt)
                break
            except ValueError:
                continue
        else:
            raise serializers.ValidationError(
                f"Invalid format. Allowed: {', '.join(self.formats)}"
            )

        # 2. Apply default time if missing
        if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
            parsed = parsed.replace(
                hour=self.default_time[0],
                minute=self.default_time[1],
                second=self.default_time[2]
            )

        # 3. Return the Jalali object itself (not togregorian)
        return parsed

    def to_representation(self, value):
        if value is None:
            return None
        # Convert Gregorian datetime back to Jalali if needed
        if isinstance(value, datetime.datetime):
            jalali_dt = jdatetime.datetime.fromgregorian(datetime=value)
        else:
            jalali_dt = value  # already a jdatetime
        return jalali_dt.strftime(self.formats[0])


class DynamicRequestSerializer(serializers.Serializer):

    type_mapping = {
        "string": serializers.CharField,
        "integer": serializers.IntegerField,
        "boolean": serializers.BooleanField,
        "date": serializers.DateField,
        "jdate": lambda **kwargs: JalaliDateTimeField(formats=['%Y/%m/%d %H:%M:%S'], **kwargs),
        "list_string": lambda **kwargs: serializers.ListField(child=serializers.CharField(), **kwargs),
        "list_integer": lambda **kwargs: serializers.ListField(child=serializers.IntegerField(), **kwargs)
    }
        
    def __init__(self, *args, **kwargs):
        request_foreign = kwargs.pop('request_foreign', None)
        super().__init__(*args, **kwargs)
        
        if request_foreign:
            
            for param, type in request_foreign.get_query_parameters().items():
                self.fields[param] = self.type_mapping[type](required=False)

            for param, type in request_foreign.get_body_parameters().items():
                self.fields[param] = self.type_mapping[type](required=False)

class SendCodeSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    type = serializers.CharField()
