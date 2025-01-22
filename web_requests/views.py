import os
from django.conf import settings
import json
import requests
from rest_framework import viewsets
from rest_framework.response import Response
from django.http import HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .serializers import SendCodeSerializer, LoginSerializer, cm10Serializer
from .models import RequestLog


class SendSMSCodeViewSeHamkadeh(viewsets.ViewSet):
    def create(self, request):
        serializer = SendCodeSerializer(data=request.data)
        if serializer.is_valid():
            response = requests.post('https://api.hamkadeh.com/api/auth/login/send-code', json=serializer.validated_data)
            log = RequestLog.objects.create(
                username=serializer.validated_data['username'],
                request_type='send_code',
                request_data=serializer.validated_data,
                response_data=response.json()
            )
            return Response(response.json())
        return Response(serializer.errors, status=400)

class LoginViewSetHamkadeh(viewsets.ViewSet):
    def create(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            response = requests.post('https://api.hamkadeh.com/api/auth/login', json=serializer.validated_data)
            log = RequestLog.objects.create(
                username=serializer.validated_data['username'],
                request_type='login',
                request_data=serializer.validated_data,
                response_data=response.json()
            )
            token = response.json().get('token')
            if token:
                request.session['token'] = token
                request.session['username'] = serializer.validated_data['username']
                # request.session['token'] = response.data.get('token')
            return Response(response.json())
        return Response(serializer.errors, status=400)
    

class cm10(viewsets.ViewSet):
    def create(self, request):
        serializer = cm10Serializer(data=request.data)
        if serializer.is_valid():
            token = request.session.get('token')
            headers = {
                'Authorization': f'Bearer {token}'
            }
            params = {
                'export_data': serializer.validated_data['export_data'],
                'call_type[]': serializer.validated_data['call_type'],
                'start_at': serializer.validated_data['start_at'],
                'end_at': serializer.validated_data['end_at']
            }
            response = requests.post('https://api.hamkadeh.com/api/accounting/call-log/index', headers=headers, params=params)
            
            response_data = ""

            if response.headers.get('Content-Type') == 'application/json':
                try:
                    return Response(response.json())
                except json.JSONDecodeError:
                    return Response(response.text, status=response.status_code)
            else:
                return Response(response.text, status=response.status_code)

            log = RequestLog.objects.create(
                username=request.session.get('username'),
                request_type='POST',
                request_data=serializer.validated_data,
                response_data=response_data,
                additional_info={'status_code': response.status_code}
            )

            return Response(response.json())
        return Response(serializer.errors, status=400)
    

# @csrf_exempt
# def simulate_request_cm10(request):
#     try:
#         body = json.loads(request.body)
#         start_at = body.get('start_at')
#         end_at = body.get('end_at')
#         token = request.headers.get('cookie').split('token=')[1].split(';')[0]

#         # Send the POST request to the target server
#         url = "https://api.hamkadeh.com/api/accounting/call-log/index"
#         data = {
#             'export_data': 1,
#             'call_type[]': 1,
#             'start_at': start_at,
#             'end_at': end_at
#         }
#         headers = {
#             'Authorization': f'Bearer {token}',
#             'Content-Type': 'application/x-www-form-urlencoded',
#             'Accept-Encoding': 'br'
#         }
#         response = requests.post(url, data=data, headers=headers)

#         # Decode Brotli content if necessary
#         if response.headers.get('content-encoding') == 'br':
#             content = brotli.decompress(response.content)
#         else:
#             content = response.content

#         # Extract filename from Content-Disposition header
#         content_disposition = response.headers.get('content-disposition')
#         if content_disposition:
#             filename = content_disposition.split('filename=')[1].strip('"')
#         else:
#             filename = "data.xlsx"

#         # Return the response as an Excel file
#         excel_response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
#         excel_response['Content-Disposition'] = f'attachment; filename="{filename}"'
#         return excel_response
#     except json.JSONDecodeError as e:
#         return HttpResponse(f"JSON decode error: {e}", status=400)
#     except Exception as e:
#         return HttpResponse(f"Error: {e}", status=500)