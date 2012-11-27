from django.shortcuts import render_to_response
#from django.http import HttpResponse
from django.template import RequestContext

def rr(template, request, args):
    return render_to_response(template, args, RequestContext(request))

def index(request):
    return rr('index.html', request, {})
