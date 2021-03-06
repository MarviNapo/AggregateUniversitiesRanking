# -*- coding: utf8 -*- 

import datetime
import os
import codecs
import csv
#import xlwt
from functools import reduce
from zipfile import ZipFile, ZIP_DEFLATED
from gzip import GzipFile
from StringIO import StringIO
from cStringIO import StringIO as BytesIO
from django.shortcuts import render
from django.core.context_processors import csrf
from django.core.servers.basehttp import FileWrapper
from django.conf import settings
from django.http import HttpResponse
from django.core.cache import caches
from rest_framework import serializers
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pandas import DataFrame, ExcelWriter
import pandas as pd
from .models import RankingDescription, RankingValue, University, Result, BigSiteText
from .name_matching import ranking_descriptions, build_aggregate_ranking_dataframe, assemble_aggregate_ranking_dataframe
from forms import SelectRankingsNamesAndYear

# Create your views here.

START_AGGREGATE_YEAR = getattr(settings, 'START_AGGREGATE_YEAR', 2014)
FINISH_AGGREGATE_YEAR = getattr(settings, 'FINISH_AGGREGATE_YEAR', datetime.date.today().year)

BASE_DIR = getattr(settings, 'BASE_DIR')
current_dir = os.path.join(BASE_DIR, 'aggregate_ranking_representation')
csv_files_dir_relative_path = os.path.join('static', 'csv')
csv_files_dir = os.path.join(current_dir, csv_files_dir_relative_path)

lang_list = ['En', 'Ru'] # Will be from app config or database!!!

def prepare_ranktable_to_response(aggregate_ranking_dataframe):
    ranktable = list()
    columns_names = aggregate_ranking_dataframe.columns.tolist()
    records = aggregate_ranking_dataframe.to_dict('records')
    ranktable.append(columns_names)
    for record in records:
        table_row = list()
        for column_name in columns_names:
            table_row.append(record[column_name])
        ranktable.append(table_row)
    return ranktable


def fix_columns(aggregate_ranking_dataframe):
    aggregate_ranking_dataframe = aggregate_ranking_dataframe.rename(columns={'aggregate_rank' : 'Aggregate Rank', 'rank' : 'Rank', 'university_name' : 'University Name'})
    right_ordered_columns = ['Rank', 'Aggregate Rank', 'University Name']
    tail = [column_name for column_name in aggregate_ranking_dataframe.columns.tolist() if column_name not in right_ordered_columns]
    right_ordered_columns.extend(tail)
    return aggregate_ranking_dataframe[right_ordered_columns]



def calculate_correlation_matrix(aggregate_ranking_dataframe):
    dataframe_prepared_for_calculate_correlation = aggregate_ranking_dataframe.drop('University Name', axis=1)
    return dataframe_prepared_for_calculate_correlation.corr(method='spearman')



def prepare_correlation_matrix_to_response(correlation_matrix):
    print 'Entry in prepare_correlation_matrix_to_response'
    correlation_matrix_table = list()
    table_first_row = [' ']
    columns_names = correlation_matrix.columns.tolist()
    right_ordered_columns = ['Rank', 'Aggregate Rank']
    tail = [column_name for column_name in columns_names if column_name not in right_ordered_columns]
    right_ordered_columns.extend(tail)
    table_first_row.extend(right_ordered_columns)
    correlation_matrix_table.append(table_first_row)
    records = correlation_matrix.to_dict()
    for column_name in right_ordered_columns:
        table_row = [column_name]
        record = records[column_name]
        for column_name in right_ordered_columns:
            table_row.append(float('{0:.2f}'.format(record[column_name])))
        correlation_matrix_table.append(table_row)
        
    return correlation_matrix_table



def assemble_csv_filename(selected_rankings_names, year):
    selected_rankings_names = sorted(selected_rankings_names)
    csv_filename = reduce(lambda filename, rankname: filename + rankname + '_', selected_rankings_names, str()) + str(year) + '.csv'
    return csv_filename.lower()


def assemble_filename(selected_rankings_names, year, data_type, file_type=None):
    print 'Entry in assemble_filename'
    selected_rankings_names = sorted(selected_rankings_names)
    filename = data_type + '_' +  reduce(lambda filename, rankname: filename + rankname + '_', selected_rankings_names, str()) + str(year)
    if file_type != None:
        filename = filename + '.' + file_type
    print 'assemble_filename, filename: ', filename.lower()
    return filename.lower()


def to_mem_excel(dataframe, sheet_name='WorkSheet'):
    iobuffer = BytesIO()
    writer = ExcelWriter(iobuffer, engine='xlwt')
    dataframe.to_excel(writer, sheet_name=sheet_name)
    writer.save()
    iobuffer.flush()
    iobuffer.seek(0)
    return iobuffer.getvalue()

def to_mem_csv(dataframe, index=False, sep=';'):
    iobuffer = BytesIO()
    dataframe.to_csv(iobuffer, index=index, sep=sep, encoding='utf-8')
    iobuffer.flush()
    iobuffer.seek(0)
    return iobuffer.getvalue()

def to_gzip(data):
    iobuffer = StringIO()
    gzip_mem_object = GzipFile(mode='wb', compresslevel=6, fileobj=iobuffer)
    gzip_mem_object.write(data)
    gzip_mem_object.flush()
    gzip_mem_object.close()
    return iobuffer.getvalue()



class Storage(object):

    def __init__(self):
        #self.cache = caches['default']
        self.storage_model = Result

    def save(self, key, value):
        item_list = self.storage_model.objects.filter(key=key)
        #if item_list == []:
        if len(item_list) == 0:
            new_stored_item = self.storage_model(key=key, value=value)
            try:
                new_stored_item.save()
            except Error as e:
                print e
        else:
            print 'len(item_list) == ', len(item_list)
        return

    def get(self, key):
        item_list = list(self.storage_model.objects.filter(key=key))
        if item_list != []:
        #if len(item_list) > 0:
            print 'storage.get, item_list != []'
            return item_list[0].value
        else:
            print 'storage.get, item_list == []'
            return None


    def delete(self, key):
        item_list = self.storage_model.objects.filter(key=key)
        #if item_list != []:
        if len(item_list) > 0:
            item = item_list[0]
            item.delete()
        return
    
    def clear(self):
        self.storage_model.objects.all().delete()


def check_file_exist(csv_file_path):
    return os.path.exists(csv_file_path)



def index(request):
    return render(request, 'aggregate_ranking_representation/base.html')


class RankingTableAPIView(APIView):

    def get(self, request, *args, **kw):
        response = Response('', status=status.HTTP_200_OK) #Must inform about error

        return response
    
    def post(self, request, format=None):
        storage = Storage()
        #storage.clear()
        request_data = request.data
        print request_data
        response_data = {'rankTable' : None, 'rankingsNamesList' : None, 'yearsList' : None, 'selectedYear' : None, 'paginationParameters' : {'recordsPerPageSelectionList' : [100, 200], 'currentPageNum' : 1, 'totalTableRecords' : 1000, 'totalPages' : 0, 'correlationMatrix' : None}}
        current_page_num = request_data.get('currentPageNum')
        if current_page_num is None:
            current_page_num = 1
        records_per_page = request_data.get('recordsPerPage')
        if records_per_page is None:
            records_per_page = response_data['paginationParameters']['recordsPerPageSelectionList'][0]
        short_rankings_names = [ranking_name.short_name for ranking_name in RankingDescription.objects.all()] #This is right!
        short_rankings_names = [ranking_name for ranking_name in short_rankings_names if ranking_name in ranking_descriptions.keys()] # This is temp?
        years = range(FINISH_AGGREGATE_YEAR, START_AGGREGATE_YEAR - 1, -1)

        selected_rankings_names = short_rankings_names

        selected_year = FINISH_AGGREGATE_YEAR # This is right!

        if (request_data['selectedRankingNames'] != None) and (request_data['selectedRankingNames'] != []):
            selected_rankings_names = request_data['selectedRankingNames']
            selected_rankings_names = [ranking_name for ranking_name in selected_rankings_names if ranking_name in ranking_descriptions.keys()] # This is temp!
            if request_data['selectedYear'] != None:
                selected_year = request_data['selectedYear']
        else:
            response_data['rankingsNamesList'] = short_rankings_names
            response_data['yearsList'] = years
            if request_data['selectedYear'] != None:
                selected_year = request_data['selectedYear']
        response_data['paginationParameters']['recordsPerPage']  = records_per_page
        response_data['paginationParameters']['currentPageNum'] = current_page_num

        response_data['selectedYear'] = selected_year

        aggregate_ranking_dataframe = DataFrame()

        print 'Before generating various storgae keys'
        aggregate_ranking_dataframe_storage_key = assemble_filename(selected_rankings_names, selected_year, 'ranktable')
        print 'Before save/retrieve aggregate_ranking_dataframe to/from storage'

        print 'aggregate_ranking_dataframe_storage_key: ', aggregate_ranking_dataframe_storage_key



        saved_aggregate_ranking_dataframe = storage.get(aggregate_ranking_dataframe_storage_key)
        if saved_aggregate_ranking_dataframe == None:
            print 'before call assemble_aggregate_ranking_dataframe'
            aggregate_ranking_dataframe = assemble_aggregate_ranking_dataframe(selected_rankings_names, int(selected_year))
            aggregate_ranking_dataframe = fix_columns(aggregate_ranking_dataframe)
            storage.save(key=aggregate_ranking_dataframe_storage_key, value=to_mem_csv(aggregate_ranking_dataframe))

        else:
            print 'saved_aggregate_ranking_dataframe != None'
            print 'retrieve aggregate_ranking_dataframe from storage'
            aggregate_ranking_dataframe = pd.read_csv(StringIO(saved_aggregate_ranking_dataframe), sep=';', encoding='utf-8', index_col=None)


        correlation_matrix = DataFrame()
        correlation_matrix_storage_key = assemble_filename(selected_rankings_names, selected_year, 'correlation')

        print 'Before save/retrieve correlation_matrix to/from storage'
        print 'correlation_matrix_storage_key: ', correlation_matrix_storage_key

        saved_correlation_matrix = storage.get(correlation_matrix_storage_key)
        if saved_correlation_matrix == None:
            print 'before call calculate_correlation_matrix'
            correlation_matrix = calculate_correlation_matrix(aggregate_ranking_dataframe)
            storage.save(key=correlation_matrix_storage_key, value=to_mem_csv(correlation_matrix, index=True))
        else:
            print 'saved_correlation_matrix != None'
            print 'retrieve correlation_matrix from storage'
            correlation_matrix = pd.read_csv(StringIO(saved_correlation_matrix), sep=';', encoding='utf-8', index_col=0)


        #prepared_for_response_correlation_matrix = None
        #if request_data['needsToBeUpdated']:
        #    prepared_for_response_correlation_matrix = prepare_correlation_matrix_to_response(correlation_matrix)
        #else:
        #    prepared_for_response_correlation_matrix = None

        print 'Before call prepare_correlation_matrix_to_response'
        prepared_for_response_correlation_matrix = prepare_correlation_matrix_to_response(correlation_matrix)
        print 'After call prepare_correlation_matrix_to_response'
        response_data['correlationMatrix'] = prepared_for_response_correlation_matrix

        aggregate_ranking_dataframe_len = aggregate_ranking_dataframe.count()[0]
        if records_per_page >= aggregate_ranking_dataframe_len:
            current_page_num = 1

        last_page_record_num = current_page_num * records_per_page
        first_page_record_num = last_page_record_num - records_per_page
        
        if last_page_record_num > aggregate_ranking_dataframe_len:
            last_page_record_num = aggregate_ranking_dataframe_len

        #ranktable = prepare_ranktable_to_response(selected_rankings_names, aggregate_ranking_dataframe[first_page_record_num:last_page_record_num])
        ranktable = prepare_ranktable_to_response(aggregate_ranking_dataframe[first_page_record_num:last_page_record_num])
        total_records = aggregate_ranking_dataframe_len
        total_pages = total_records / records_per_page 

        if total_records % records_per_page > 0:
            total_pages = total_pages + 1

        response_data['paginationParameters']['totalPages'] = total_pages
        response_data['rankTable'] = ranktable
        
        print 'Before creating response'
        response = Response(response_data, status=status.HTTP_200_OK)
        print 'After creating response and before return'

        return response


class FileDownloadAPIView(APIView):

    def get(self, request, *args, **kw):
        response = Response('', status=status.HTTP_200_OK) #Must inform about error

        return response
    
    def post(self, request, format=None):
        storage = Storage()
        request_data = request.data
        
        selected_rankings_names = request_data.get('selectedRankingNames') 
        print 'FileDownloadAPIView post, selected_rankings_names: ', selected_rankings_names
        selected_year = request_data.get('selectedYear')
        data_type = request_data.get('dataType')
        file_type = request_data.get('fileType')

        if selected_year == None or (selected_year != None and (selected_year > FINISH_AGGREGATE_YEAR or selected_year < START_AGGREGATE_YEAR)):
            selected_year = FINISH_AGGREGATE_YEAR

        short_rankings_names = [ranking_name.short_name for ranking_name in RankingDescription.objects.all()] #This is right!
        short_rankings_names = [ranking_name for ranking_name in short_rankings_names if ranking_name in ranking_descriptions.keys()] # This is temp?

        if selected_rankings_names == []:
            selected_rankings_names = short_rankings_names

        if data_type != None:
            data_type = data_type.lower()
        else:
            data_type = 'ranktable'

        if file_type != None:
            file_type = file_type.lower()
        else:
            file_type = 'csv'

        #storage_key = assemble_filename(selected_rankings_names, selected_year, data_type, file_type)
        storage_key = assemble_filename(selected_rankings_names, selected_year, data_type)
        print 'FileDownloadAPIView post, storage_key: ', storage_key
        #download_file_data = storage.get(storage_key)
        download_file_buffer = storage.get(storage_key)
        #print 'download_file_buffer', download_file_buffer
        download_file_data = None
        if file_type == 'csv':
            print 'FileDownloadAPIView, post, file_type == \'csv\', before call to_gzip'
            download_file_data = to_gzip(download_file_buffer.encode('utf-8'))
            print 'FileDownloadAPIView post method, after create download_file_data'
        elif file_type == 'xls':
            print 'FileDownloadAPIView, post, file_type == \'csv\', before call to_gzip'
            if data_type == 'ranktable':
                dataframe = pd.read_csv(StringIO(download_file_buffer), sep=';', encoding='utf-8', index_col=None)
                download_file_data = to_gzip(to_mem_excel(dataframe))
            else:
                dataframe = pd.read_csv(StringIO(download_file_buffer), sep=';', encoding='utf-8', index_col=0)
                download_file_data = to_gzip(to_mem_excel(dataframe))
               
       
        print 'FileDownloadAPIView post method, after fill download_file_data'

        response = HttpResponse(download_file_data)
        response['Content-Encoding'] = 'gzip'
        response['Content-Length'] = str(len(download_file_data))
        return response

class BigSiteTextsAPIView(APIView):

    def get(self, request, *args, **kw):
        print 'Entry in BigSiteTextsAPIView get method'
        response_data = {
                'methodologyTextEn' : None,
                'methodologyTextRu' : None,
                'aboutTextEn' : None,
                'aboutTextRu' : None
                }
        methodology_texts = BigSiteText.objects.filter(text_name='methodology')
        about_texts = BigSiteText.objects.filter(text_name='about')
        
        for lang in lang_list:
            methodology_text_list = list(methodology_texts.filter(lang=lang))
            about_text_list = list(about_texts.filter(lang=lang))
            if methodology_text_list != []:
                response_data['methodologyText%s' % lang] = methodology_text_list[0].text
            if about_text_list != []:
                response_data['aboutText%s' % lang] = about_text_list[0].text
       
        #response = Response('', status=status.HTTP_404_NOT_FOUND) #Must inform about error
        response = Response(response_data, status=status.HTTP_200_OK)
        return response

    def post(self, request, format=None):
        print 'Entry in BigSiteTextsAPIView post method'
        response_data = {'methodologyTextEn' : None, 'methodologyTextRu' : None}
        methodology_texts = BigSiteText.objects.filter(text_name='methodology')

        for lang in lang_list:
            methodology_text_list = list(methodology_texts.filter(lang=lang))
            if methodology_text_list != []:
                response_data['methodologyText%s' % lang] = methodology_text_list[0].text
        response = Response(response_data, status=status.HTTP_200_OK)

        return response

