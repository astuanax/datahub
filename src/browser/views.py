import codecs
import csv
import json
import os
import re
import urllib
import uuid

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.context_processors import csrf
from django.http import *
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt

from thrift.protocol import TBinaryProtocol
from thrift.protocol import TJSONProtocol
from thrift.transport.TTransport import TMemoryBuffer

from inventory.models import App, Card
from account.utils import grant_app_permission
from core.db.manager import DataHubManager
from datahub import DataHub
from datahub.account import AccountService
from service.handler import DataHubHandler
from utils import *

'''
@author: Anant Bhardwaj
@date: Mar 21, 2013

Datahub Web Handler
'''

handler = DataHubHandler()
core_processor = DataHub.Processor(handler)
account_processor = AccountService.Processor(handler)


def home(request):
    try:
        username = request.user.get_username()
        if username:
            return HttpResponseRedirect('/browse/%s' % (username))
        else:
            return HttpResponseRedirect('/www')
    except Exception as e:
        return HttpResponse(
            json.dumps({'error': str(e)}),
            content_type="application/json")

# just for backward compatibility


def about(request):
    return HttpResponseRedirect('/www')


'''
APIs and Services
'''


@csrf_exempt
def service_core_binary(request):
        # Catch CORS preflight requests
    if request.method == 'OPTIONS':
        resp = HttpResponse('')
        resp['Content-Type'] = 'text/plain charset=UTF-8'
        resp['Content-Length'] = 0
        resp.status_code = 204
    else:
        try:
            iprot = TBinaryProtocol.TBinaryProtocol(
                TMemoryBuffer(request.body))
            oprot = TBinaryProtocol.TBinaryProtocol(TMemoryBuffer())
            core_processor.process(iprot, oprot)
            resp = HttpResponse(oprot.trans.getvalue())

        except Exception as e:
            resp = HttpResponse(
                json.dumps({'error': str(e)}),
                content_type="application/json")
    try:
        resp['Access-Control-Allow-Origin'] = request.META['HTTP_ORIGIN']
    except:
        pass
    resp['Access-Control-Allow-Methods'] = "POST, PUT, GET, DELETE, OPTIONS"
    resp['Access-Control-Allow-Credentials'] = "true"
    resp['Access-Control-Allow-Headers'] = ("Authorization, Cache-Control, "
                                            "If-Modified-Since, Content-Type")

    return resp


@csrf_exempt
def service_account_binary(request):
    # Catch CORS preflight requests
    if request.method == 'OPTIONS':
        resp = HttpResponse('')
        resp['Content-Type'] = 'text/plain charset=UTF-8'
        resp['Content-Length'] = 0
        resp.status_code = 204
    else:
        try:
            iprot = TBinaryProtocol.TBinaryProtocol(
                TMemoryBuffer(request.body))
            oprot = TBinaryProtocol.TBinaryProtocol(TMemoryBuffer())
            account_processor.process(iprot, oprot)
            resp = HttpResponse(oprot.trans.getvalue())

        except Exception as e:
            resp = HttpResponse(
                json.dumps({'error': str(e)}),
                content_type="application/json")

    try:
        resp['Access-Control-Allow-Origin'] = request.META['HTTP_ORIGIN']
    except:
        pass
    resp['Access-Control-Allow-Methods'] = "POST, PUT, GET, DELETE, OPTIONS"
    resp['Access-Control-Allow-Credentials'] = "true"
    resp['Access-Control-Allow-Headers'] = ("Authorization, Cache-Control, "
                                            "If-Modified-Since, Content-Type")

    return resp


@csrf_exempt
def service_core_json(request):
    # Catch CORS preflight requests
    if request.method == 'OPTIONS':
        resp = HttpResponse('')
        resp['Content-Type'] = 'text/plain charset=UTF-8'
        resp['Content-Length'] = 0
        resp.status_code = 204
    else:
        try:
            iprot = TJSONProtocol.TJSONProtocol(TMemoryBuffer(request.body))
            oprot = TJSONProtocol.TJSONProtocol(TMemoryBuffer())
            core_processor.process(iprot, oprot)
            resp = HttpResponse(
                oprot.trans.getvalue(),
                content_type="application/json")

        except Exception as e:
            resp = HttpResponse(
                json.dumps({'error': str(e)}),
                content_type="application/json")

    try:
        resp['Access-Control-Allow-Origin'] = request.META['HTTP_ORIGIN']
    except:
        pass
    resp['Access-Control-Allow-Methods'] = "POST, PUT, GET, DELETE, OPTIONS"
    resp['Access-Control-Allow-Credentials'] = "true"
    resp['Access-Control-Allow-Headers'] = ("Authorization, Cache-Control, "
                                            "If-Modified-Since, Content-Type")

    return resp


'''
Repository Base
'''


@login_required
def user(request, repo_base):
    try:
        username = request.user.get_username()

        res = DataHubManager.has_base_privilege(username, repo_base, 'CONNECT')
        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        manager = DataHubManager(user=repo_base)
        repos = manager.list_repos()

        visible_repos = []

        for repo in repos:
            res = manager.list_collaborators(repo_base, repo)

            collaborators = [(c[0].split('=')[0]).strip()
                             for c in res['tuples']]
            collaborators = filter(
                lambda x: x != '' and x != repo_base, collaborators)

            if username not in collaborators and username != repo_base:
                continue

            visible_repos.append({
                'name': repo,
                'owner': repo_base,
                'public': True if 'PUBLIC' in collaborators else False,
                'collaborators': collaborators,
                'collaborators_str': ', '.join(collaborators),
                'num_collaborators': len(collaborators)
            })

        return render_to_response("user-browse.html", {
            'login': username,
            'repo_base': repo_base,
            'repos': visible_repos})

    except Exception as e:
        return HttpResponse(json.dumps(
            {'error': str(e)}),
            content_type="application/json")


'''
Repository
'''


@login_required
def repo(request, repo_base, repo):
    return HttpResponseRedirect(
        '/browse/%s/%s/tables' % (repo_base, repo))


@login_required
def repo_tables(request, repo_base, repo):
    try:
        username = request.user.get_username()

        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'USAGE')
        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        # get the base tables and views of the user's repo
        manager = DataHubManager(user=repo_base)
        base_tables = manager.list_tables(repo)
        views = manager.list_views(repo)

        res = {
            'login': username,
            'repo_base': repo_base,
            'repo': repo,
            'base_tables': base_tables,
            'views': views}

        res.update(csrf(request))
        return render_to_response("repo-browse-tables.html", res)

    except Exception as e:
        return HttpResponse(json.dumps(
            {'error': str(e)}),
            content_type="application/json")


@login_required
def repo_files(request, repo_base, repo):
    try:
        username = request.user.get_username()

        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'USAGE')
        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        repo_dir = '/user_data/%s/%s' % (repo_base, repo)
        if not os.path.exists(repo_dir):
            os.makedirs(repo_dir)

        uploaded_files = [f for f in os.listdir(repo_dir)]

        res = {
            'login': username,
            'repo_base': repo_base,
            'repo': repo,
            'files': uploaded_files}

        res.update(csrf(request))
        return render_to_response("repo-browse-files.html", res)

    except Exception as e:
        return HttpResponse(json.dumps(
            {'error': str(e)}),
            content_type="application/json")


@login_required
def repo_cards(request, repo_base, repo):
    try:
        username = request.user.get_username()

        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'USAGE')
        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        cards = Card.objects.all().filter(
            repo_base=repo_base, repo_name=repo)

        cards = [c.card_name for c in cards]

        res = {
            'login': username,
            'repo_base': repo_base,
            'repo': repo,
            'cards': cards}

        res.update(csrf(request))
        return render_to_response("repo-browse-cards.html", res)

    except Exception as e:
        return HttpResponse(json.dumps(
            {'error': str(e)}),
            content_type="application/json")


@login_required
def repo_create(request, repo_base):
    try:
        username = request.user.get_username()
        if request.method == "POST":
            if username != repo_base:
                raise Exception(
                    'Permission denied. '
                    '%s can\'t create new repository in %s.'
                    % (username, repo_base)
                    )

            repo = request.POST['repo']
            manager = DataHubManager(user=repo_base)
            manager.create_repo(repo)

            return HttpResponseRedirect('/browse/%s' % (repo_base))

        else:
            res = {'repo_base': repo_base, 'login': username}
            res.update(csrf(request))
            return render_to_response("repo-create.html", res)

    except Exception as e:
        return HttpResponse(json.dumps(
            {'error': str(e)}),
            content_type="application/json")


@login_required
def repo_delete(request, repo_base, repo):
    try:
        username = request.user.get_username()

        if username != repo_base:
            raise Exception(
                'Permission denied. '
                '%s can\'t delete repository %s in %s.'
                % (username, repo, repo_base)
                )

        manager = DataHubManager(user=repo_base)
        manager.delete_repo(repo=repo, force=True)
        return HttpResponseRedirect('/browse/%s' % (repo_base))
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


@login_required
def repo_settings(request, repo_base, repo):
    try:
        username = request.user.get_username()
        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'CREATE')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        manager = DataHubManager(user=repo_base)
        res = manager.list_collaborators(repo_base, repo)

        collaborators = [(c[0].split('=')[0]).strip() for c in res['tuples']]
        collaborators = filter(lambda x: x != '' and x !=
                               repo_base, collaborators)

        res = {
            'login': username,
            'repo_base': repo_base,
            'repo': repo,
            'collaborators': collaborators}
        res.update(csrf(request))
        return render_to_response("repo-settings.html", res)
    except Exception as e:
        return HttpResponse(json.dumps(
            {'error': str(e)}),
            content_type="application/json")


@login_required
def repo_collaborators_add(request, repo_base, repo):
    try:
        username = request.user.get_username()
        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'CREATE')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        collaborator_username = request.POST['collaborator_username']
        manager = DataHubManager(user=repo_base)
        manager.add_collaborator(
            repo, collaborator_username,
            privileges=['SELECT', 'INSERT', 'UPDATE'])
        return HttpResponseRedirect('/settings/%s/%s' % (repo_base, repo))
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


@login_required
def repo_collaborators_remove(request, repo_base, repo, collaborator_username):
    try:
        username = request.user.get_username()
        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'CREATE')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        manager = DataHubManager(user=repo_base)
        manager.delete_collaborator(repo, collaborator_username)
        return HttpResponseRedirect('/settings/%s/%s' % (repo_base, repo))
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


'''
Tables
'''


@login_required
def table(request, repo_base, repo, table):
    try:
        username = request.user.get_username()
        dh_table_name = '%s.%s.%s' % (repo_base, repo, table)

        res = DataHubManager.has_table_privilege(
            username, repo_base, dh_table_name, 'SELECT')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        manager = DataHubManager(user=repo_base)
        res = manager.execute_sql(
            query='EXPLAIN SELECT * FROM %s' % (dh_table_name))

        limit = 50

        num_rows = re.match(r'.*rows=(\d+).*', res['tuples'][0][0]).group(1)
        count = int(num_rows)

        total_pages = 1 + (int(count) / limit)

        current_page = 1
        try:
            current_page = int(request.POST['page'])
        except:
            pass

        if current_page < 1:
            current_page = 1

        start_page = current_page - 5
        if start_page < 1:
            start_page = 1

        end_page = start_page + 10

        if end_page > total_pages:
            end_page = total_pages

        res = manager.execute_sql(
            query='SELECT * from %s LIMIT %s OFFSET %s'
            % (dh_table_name, limit, (current_page - 1) * limit))

        column_names = [field['name'] for field in res['fields']]
        tuples = res['tuples']

        annotation_text = None
        url_path = '/browse/%s/%s/table/%s' % (repo_base, repo, table)
        try:
            annotation = Annotation.objects.get(url_path=url_path)
            annotation_text = annotation.annotation_text
        except:
            pass

        data = {
            'login': username,
            'repo_base': repo_base,
            'repo': repo,
            'table': table,
            'column_names': column_names,
            'tuples': tuples,
            'annotation': annotation_text,
            'current_page': current_page,
            'next_page': current_page + 1,
            'prev_page': current_page - 1,
            'url_path': url_path,
            'total_pages': total_pages,
            'pages': range(start_page, end_page + 1)}

        data.update(csrf(request))
        return render_to_response("table-browse.html", data)
    except Exception as e:
        return HttpResponse(json.dumps(
            {'error': str(e)}),
            content_type="application/json")


@login_required
def table_export(request, repo_base, repo, table_name):
    try:
        username = request.user.get_username()
        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'CREATE')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        repo_dir = '/user_data/%s/%s' % (repo_base, repo)

        if not os.path.exists(repo_dir):
            os.makedirs(repo_dir)

        file_path = '%s/%s.csv' % (repo_dir, table_name)
        dh_table_name = '%s.%s.%s' % (repo_base, repo, table_name)
        DataHubManager.export_table(
            repo_base=repo_base, table_name=dh_table_name, file_path=file_path)
        return HttpResponseRedirect('/browse/%s/%s/files' % (repo_base, repo))
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


@login_required
def table_delete(request, repo_base, repo, table_name):
    try:
        username = request.user.get_username()
        dh_table_name = '%s.%s.%s' % (repo_base, repo, table_name)

        res = DataHubManager.has_table_privilege(
            username, repo_base, dh_table_name, 'DELETE')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        manager = DataHubManager(user=repo_base)

        query = '''DROP TABLE %s''' % (dh_table_name)
        manager.execute_sql(query=query)
        return HttpResponseRedirect('/browse/%s/%s' % (repo_base, repo))
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


'''
Files
'''


def file_save(repo_base, repo, data_file):
    repo_dir = '/user_data/%s/%s' % (repo_base, repo)
    if not os.path.exists(repo_dir):
        os.makedirs(repo_dir)

    file_name = '%s/%s' % (repo_dir, data_file.name)
    with open(file_name, 'wb+') as destination:
        for chunk in data_file.chunks():
            destination.write(chunk)


@login_required
def file_upload(request, repo_base, repo):
    try:
        data_file = request.FILES['data_file']
        file_save(repo_base, repo, data_file)
        return HttpResponseRedirect('/browse/%s/%s/files' % (repo_base, repo))
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


@login_required
def file_import(request, repo_base, repo, file_name):
    try:
        username = request.user.get_username()
        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'CREATE')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        delimiter = str(request.GET['delimiter'])
        if delimiter == '':
            delimiter = str(request.GET['other_delimiter'])

        header = True if request.GET['has_header'] == "true" else False

        quote_character = request.GET['quote_character']
        if quote_character == '':
            quote_character = request.GET['other_quote_character']

        delimiter = delimiter.decode('string_escape')

        repo_dir = '/user_data/%s/%s' % (repo_base, repo)
        file_path = '%s/%s' % (repo_dir, file_name)
        table_name, _ = os.path.splitext(file_name)
        table_name = clean_str(table_name, 'table')
        dh_table_name = '%s.%s.%s' % (repo_base, repo, table_name)

        f = codecs.open(file_path, 'r', 'ISO-8859-1')

        data = csv.reader(f, delimiter=delimiter)
        cells = data.next()

        columns = [clean_str(str(i), 'col') for i in range(0, len(cells))]
        if header:
            columns = map(lambda x: clean_str(x, 'col'), cells)

        columns = rename_duplicates(columns)

        query = 'CREATE TABLE %s (%s text' % (dh_table_name, columns[0])

        for i in range(1, len(columns)):
            query += ', %s %s' % (columns[i], 'text')
        query += ')'

        manager = DataHubManager(user=repo_base)
        manager.execute_sql(query=query)
        manager.import_file(
            repo_base=repo_base,
            table_name=dh_table_name,
            file_path=file_path,
            delimiter=delimiter,
            header=header,
            quote_character=quote_character)
        return HttpResponseRedirect('/browse/%s/%s' % (repo_base, repo))
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


@login_required
def file_delete(request, repo_base, repo, file_name):
    try:
        username = request.user.get_username()
        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'CREATE')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        repo_dir = '/user_data/%s/%s' % (repo_base, repo)
        file_path = '%s/%s' % (repo_dir, file_name)
        os.remove(file_path)
        return HttpResponseRedirect('/browse/%s/%s/files' % (repo_base, repo))
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


@login_required
def file_download(request, repo_base, repo, file_name):
    try:
        username = request.user.get_username()
        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'USAGE')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        repo_dir = '/user_data/%s/%s' % (repo_base, repo)
        file_path = '%s/%s' % (repo_dir, file_name)
        response = HttpResponse(
            open(file_path).read(), content_type='application/force-download')
        response[
            'Content-Disposition'] = 'attachment; filename="%s"' % (file_name)
        return response
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


'''
Query
'''


@login_required
def query(request, repo_base, repo):
    try:
        username = request.user.get_username()
        data = {
            'login': username,
            'repo_base': repo_base,
            'repo': repo,
            'select_query': False,
            'query': None}

        data.update(csrf(request))

        query = get_or_post(request, key='q', fallback=None)

        if query:
            query = query.strip().rstrip(';')

            manager = DataHubManager(user=repo_base)

            select_query = False
            if (query.split()[0]).lower() == 'select':
                select_query = True

            count = 0
            limit = 50

            if select_query:
                res = manager.execute_sql(query='EXPLAIN %s' % (query))
                num_rows = re.match(r'.*rows=(\d+).*',
                                    res['tuples'][0][0]).group(1)
                count = int(num_rows)

            total_pages = 1 + (int(count) / limit)

            current_page = get_or_post(request, key='page', fallback=1)

            if current_page < 1:
                current_page = 1

            start_page = current_page - 5
            if start_page < 1:
                start_page = 1

            end_page = start_page + 10

            if end_page > total_pages:
                end_page = total_pages
            db_query = query

            if select_query:
                # wrap query in another select statement, to allow the
                # user's LIMIT statements to still work
                db_query = 'select * from (' + query + \
                    ') as BXCQWVPEMWVKFBEBNKZSRPYBSB'

                # wrap in datahub limit and offset statements, to support
                # pagination
                db_query = '%s LIMIT %s OFFSET %s' % (
                    db_query, limit, (current_page - 1) * limit)

            res = manager.execute_sql(query=db_query)

            if select_query or res['row_count'] > 0:
                column_names = [field['name'] for field in res['fields']]
                tuples = res['tuples']
            else:
                column_names = ['status']
                tuples = [['success' if res['status'] else res['error']]]

            url_path = '/browse/%s/%s/query' % (repo_base, repo)

            data.update({
                'select_query': select_query,
                'query': query,
                'column_names': column_names,
                'tuples': tuples,
                'url_path': url_path,
                'current_page': current_page,
                'next_page': current_page + 1,
                'prev_page': current_page - 1,
                'total_pages': total_pages,
                'pages': range(start_page, end_page + 1)})
            return render_to_response("query-browse-results.html", data)
        else:
            return render_to_response("query.html", data)
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


'''
Annotations
'''


@login_required
def create_annotation(request):
    try:
        url = request.POST['url']
        annotation_text = request.POST['annotation']

        try:
            annotation = Annotation.objects.get(url_path=url)
            annotation.annotation_text = annotation_text
            annotation.save()
        except Annotation.DoesNotExist:
            annotation = Annotation(
                url_path=url, annotation_text=annotation_text)
            annotation.save()

        return HttpResponseRedirect(url)
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


'''
Cards
'''


@login_required
def card(request, repo_base, repo, card_name):
    try:
        username = request.user.get_username()
        card = Card.objects.get(repo_base=repo_base,
                                repo_name=repo, card_name=card_name)
        query = card.query
        manager = DataHubManager(user=repo_base)
        res = manager.execute_sql(
            query='EXPLAIN %s' % (query))

        limit = 50

        num_rows = re.match(r'.*rows=(\d+).*', res['tuples'][0][0]).group(1)
        count = int(num_rows)
        total_pages = 1 + (int(count) / limit)

        current_page = get_or_post(request, key='page', fallback=1)

        if current_page < 1:
            current_page = 1

        start_page = current_page - 5
        if start_page < 1:
            start_page = 1

        end_page = start_page + 10

        if end_page > total_pages:
            end_page = total_pages

        # wrap query in another select statement, to allow the
        # user's LIMIT statements to still work
        db_query = 'select * from (' + query + \
            ') as BXCQWVPEMWVKFBEBNKZSRPYBSB'
        db_query = '%s LIMIT %s OFFSET %s' % (
            db_query, limit, (current_page - 1) * limit)

        res = manager.execute_sql(query=db_query)

        column_names = [field['name'] for field in res['fields']]
        tuples = res['tuples']

        annotation_text = None
        url_path = '/browse/%s/%s/card/%s' % (repo_base, repo, card_name)
        try:
            annotation = Annotation.objects.get(url_path=url_path)
            annotation_text = annotation.annotation_text
        except:
            pass

        data = {
            'login': username,
            'repo_base': repo_base,
            'repo': repo,
            'card_name': card_name,
            'annotation': annotation_text,
            'query': query,
            'column_names': column_names,
            'tuples': tuples,
            'url_path': url_path,
            'current_page': current_page,
            'next_page': current_page + 1,
            'prev_page': current_page - 1,
            'total_pages': total_pages,
            'pages': range(start_page, end_page + 1)}

        data.update(csrf(request))
        return render_to_response("card-browse.html", data)
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


# Test if this cares who calls it
@login_required
def card_create(request, repo_base, repo):
    try:
        card_name = request.POST['card-name']
        query = request.POST['query']
        url = '/browse/%s/%s/card/%s' % (repo_base, repo, card_name)

        card = Card(
            repo_base=repo_base, repo_name=repo,
            card_name=card_name, query=query)
        card.save()
        return HttpResponseRedirect(url)
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


@login_required
def card_export(request, repo_base, repo, card_name):
    try:
        username = request.user.get_username()
        card = Card.objects.get(repo_base=repo_base,
                                repo_name=repo, card_name=card_name)
        query = card.query
        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'CREATE')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        repo_dir = '/user_data/%s/%s' % (repo_base, repo)

        if not os.path.exists(repo_dir):
            os.makedirs(repo_dir)

        file_path = '%s/%s.csv' % (repo_dir, card_name)
        DataHubManager.export_query(
            repo_base=repo_base, query=query, file_path=file_path)
        return HttpResponseRedirect('/browse/%s/%s/files' % (repo_base, repo))
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


@login_required
def card_delete(request, repo_base, repo, card_name):
    try:
        username = request.user.get_username()
        res = DataHubManager.has_repo_privilege(
            username, repo_base, repo, 'CREATE')

        if not (res and res['tuples'][0][0]):
            raise Exception('Access denied. Missing required privileges.')

        card = Card.objects.get(repo_base=repo_base,
                                repo_name=repo, card_name=card_name)
        card.delete()

        return HttpResponseRedirect('/browse/%s/%s/cards' % (repo_base, repo))
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")


'''
Developer Apps
'''

# Foreign keys, migration of old users to new
@login_required
def apps(request):
    username = request.user.get_username()
    user = User.objects.get(username=username)
    user_apps = App.objects.filter(user=user)
    apps = []
    for app in user_apps:
        apps.append(
            {'app_id': app.app_id,
             'app_name': app.app_name,
             'app_token': app.app_token,
             'date_created': app.timestamp})
    print apps
    c = {
        'login': username,
        'apps': apps}
    return render_to_response('apps.html', c)


@login_required
def app_register(request):
    username = request.user.get_username()

    if request.method == "POST":
        try:
            user = User.objects.get(username=username)
            app_id = request.POST["app-id"].lower()
            app_name = request.POST["app-name"]
            app_token = str(uuid.uuid4())
            app = App(
                app_id=app_id, app_name=app_name,
                user=user, app_token=app_token)
            app.save()

            try:
                hashed_password = hashlib.sha1(app_token).hexdigest()
                DataHubManager.create_user(
                    username=app_id, password=hashed_password, create_db=False)
            except Exception as e:
                app.delete()
                raise e

            return HttpResponseRedirect('/developer/apps')
        except Exception as e:
            c = {
                'login': username,
                'errors': [str(e)]}
            c.update(csrf(request))
            return render_to_response('app-create.html', c)
    else:
        c = {'login': username}
        c.update(csrf(request))
        return render_to_response('app-create.html', c)


@login_required
def app_remove(request, app_id):
    try:
        username = request.user.get_username()
        user = User.objects.get(username=username)
        app = App.objects.get(user=user, app_id=app_id)
        app.delete()

        DataHubManager.remove_user(username=app_id)

        return HttpResponseRedirect('/developer/apps')
    except Exception as e:
        c = {'errors': [str(e)]}
        c.update(csrf(request))
        return render_to_response('apps.html', c)


@login_required
def app_allow_access(request, app_id, repo_name):
    username = request.user.get_username()
    try:
        app = None
        try:
            app = App.objects.get(app_id=app_id)
        except App.DoesNotExist:
            raise Exception("Invalid app_id")

        app = App.objects.get(app_id=app_id)

        redirect_url = get_or_post(request, key='redirect_url', fallback=None)

        if request.method == "POST":

            access_val = request.POST['access_val']

            if access_val == 'allow':
                grant_app_permission(
                    username=username,
                    repo_name=repo_name,
                    app_id=app_id,
                    app_token=app.app_token)

            if redirect_url:
                redirect_url = redirect_url + \
                    urllib.unquote_plus('?auth_user=%s' % (username))
                return HttpResponseRedirect(redirect_url)
            else:
                if access_val == 'allow':
                    return HttpResponseRedirect(
                        '/settings/%s/%s' % (username, repo_name))
                else:
                    res = {
                        'msg_title': "Access Request",
                        'msg_body':
                            "Permission denied to the app {0}.".format(app_id)
                    }
                    return render_to_response('confirmation.html', res)
        else:
            res = {
                'login': username,
                'repo_name': repo_name,
                'app_id': app_id,
                'app_name': app.app_name}

            if redirect_url:
                res['redirect_url'] = redirect_url

            res.update(csrf(request))
            return render_to_response('app-allow-access.html', res)
    except Exception as e:
        return HttpResponse(
            json.dumps(
                {'error': str(e)}),
            content_type="application/json")
