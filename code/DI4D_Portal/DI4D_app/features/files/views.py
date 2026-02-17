from django.http import HttpResponse, FileResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.urls import reverse
from django.core import signing
from django.core.signing import BadSignature
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage

from ...models import FileItem

import os
import mimetypes
import uuid
import logging

logger = logging.getLogger(__name__)
FILES_TOKEN_SALT = 'di4d-files-token'


def _encode_file_token(item_id):
    return signing.dumps({'id': int(item_id)}, salt=FILES_TOKEN_SALT)


def _decode_file_token(token):
    if not token:
        return None
    try:
        payload = signing.loads(token, salt=FILES_TOKEN_SALT)
        item_id = payload.get('id')
        if not item_id:
            return None
        return int(item_id)
    except (BadSignature, ValueError, TypeError):
        return None


@login_required(login_url='login')
def files_view(request):
    active_page = 'files'
    search_query = request.POST.get('q', '').strip() if request.method == 'POST' else request.GET.get('q', '').strip()
    file_type = request.POST.get('file_type', 'all') if request.method == 'POST' else request.GET.get('file_type', 'all')
    current_folder_token = request.POST.get('folder') if request.method == 'POST' else request.GET.get('folder')
    current_folder_id = _decode_file_token(current_folder_token)
    current_folder = None
    parent_folder_token = None

    if current_folder_id:
        current_folder = FileItem.objects.filter(id=current_folder_id, isDeleted=False, owner=request.user).select_related('parentFolder').first()
        if not current_folder:
            current_folder_token = None
            current_folder_id = None
        else:
            if current_folder.parentFolder:
                parent_folder_token = _encode_file_token(current_folder.parentFolder.id)

    breadcrumbs = [
        {
            'label': f'{request.user.username} (root)',
            'token': '',
        }
    ]
    if current_folder:
        folder_chain = []
        cursor = current_folder
        max_depth = 50
        while cursor and max_depth > 0:
            folder_chain.append(cursor)
            cursor = cursor.parentFolder
            max_depth -= 1

        for folder in reversed(folder_chain):
            breadcrumbs.append({
                'label': folder.name,
                'token': _encode_file_token(folder.id),
            })

    db_items = FileItem.objects.filter(isDeleted=False, parentFolder_id=current_folder_id, owner=request.user).select_related('owner').order_by('-id')
    file_items = []
    available_types = set()
    for item in db_items:
        is_folder = (item.s3Link or '').startswith('folders/')
        ext = os.path.splitext(item.name or '')[1].lstrip('.').lower()
        inferred_type = 'file'
        if is_folder:
            inferred_type = 'folder'
        elif ext:
            inferred_type = ext
        available_types.add(inferred_type)
        owner_name = 'Unknown'
        if item.owner:
            first_name = (item.owner.firstname or '').strip()
            last_name = (item.owner.lastname or '').strip()
            owner_name = f'{first_name} {last_name}'.strip() or item.owner.username

        file_items.append({
            'id': item.id,
            'name': item.name,
            'modified': '—',
            'modified_by': owner_name,
            'type': inferred_type,
            'token': _encode_file_token(item.id),
        })

    if search_query:
        file_items = [item for item in file_items if search_query.lower() in item['name'].lower()]

    if file_type != 'all' and file_type not in available_types:
        file_type = 'all'

    if file_type and file_type != 'all':
        file_items = [item for item in file_items if item['type'] == file_type]

    available_file_types = sorted([item_type for item_type in available_types if item_type != 'folder'])
    if 'folder' in available_types:
        available_file_types.insert(0, 'folder')

    context = {
        'active_page': active_page,
        'file_items': file_items,
        'search_query': search_query,
        'file_type': file_type,
        'available_file_types': available_file_types,
        'current_folder_token': current_folder_token,
        'current_folder_name': current_folder.name if current_folder else 'Root',
        'parent_folder_token': parent_folder_token,
        'breadcrumbs': breadcrumbs,
    }

    if request.headers.get('HX-Request') == 'true':
        return render(request, 'components/files/content_htmx.jinja', context)
    return render(request, 'sharepoint/files.jinja', context)


@login_required(login_url='login')
def files_action(request, action):
    if request.method != 'POST':
        return HttpResponse(status=405)

    action = action.strip().lower()
    payload = {
        'action': action,
        'user_id': request.user.id,
        'post': {key: request.POST.getlist(key) if len(request.POST.getlist(key)) > 1 else request.POST.get(key) for key in request.POST.keys()},
    }

    if action == 'delete':
        item_token = request.POST.get('item_token')
        current_folder_token = request.POST.get('current_folder_token')
        item_id = _decode_file_token(item_token)
        current_folder_id = _decode_file_token(current_folder_token)
        if not item_id:
            return render(request, 'components/files/feedback_htmx.jinja', {
                'message': 'No item selected for deletion.',
            })

        item = FileItem.objects.filter(id=item_id, isDeleted=False, owner=request.user).first()
        if not item:
            return render(request, 'components/files/feedback_htmx.jinja', {
                'message': 'The selected item could not be found.',
            })

        if item.s3Link and default_storage.exists(item.s3Link):
            default_storage.delete(item.s3Link)

        redirect_url = reverse('files')
        effective_folder_id = current_folder_id if current_folder_id else (item.parentFolder.id if item.parentFolder else None)
        if effective_folder_id:
            redirect_url = f'{redirect_url}?folder={_encode_file_token(effective_folder_id)}'

        item.isDeleted = True
        item.save(update_fields=['isDeleted'])

        if request.headers.get('HX-Request') == 'true':
            response = HttpResponse()
            response['HX-Redirect'] = redirect_url
            return response

        return redirect(redirect_url)

    if action == 'create-folder':
        folder_name = (request.POST.get('folder_name') or '').strip()
        if not folder_name:
            return render(request, 'components/files/feedback_htmx.jinja', {
                'message': 'Folder name is required.',
            })

        parent_folder_token = request.POST.get('parent_folder_token')
        parent_folder_id = _decode_file_token(parent_folder_token)
        parent_folder = None
        if parent_folder_id:
            parent_folder = FileItem.objects.filter(id=parent_folder_id, isDeleted=False, owner=request.user).first()

        folder_key = f"folders/user_{request.user.id}/{uuid.uuid4().hex}"
        FileItem.objects.create(
            name=folder_name,
            s3Link=folder_key,
            owner=request.user,
            parentFolder=parent_folder,
            isDeleted=False,
        )

        redirect_url = reverse('files')
        if parent_folder_id:
            redirect_url = f'{redirect_url}?folder={_encode_file_token(parent_folder_id)}'

        if request.headers.get('HX-Request') == 'true':
            response = HttpResponse()
            response['HX-Redirect'] = redirect_url
            return response

        return redirect(redirect_url)

    parent_folder_id = None
    uploaded_files = request.FILES.getlist('files')
    if uploaded_files:
        payload['uploaded_files'] = [uploaded_file.name for uploaded_file in uploaded_files]
        parent_folder_token = request.POST.get('parent_folder_token')
        parent_folder_id = _decode_file_token(parent_folder_token)
        parent_folder = None
        if parent_folder_id:
            parent_folder = FileItem.objects.filter(id=parent_folder_id, isDeleted=False, owner=request.user).first()

        stored_keys = []
        for uploaded_file in uploaded_files:
            clean_name = os.path.basename((uploaded_file.name or '').strip())
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S_%f')
            unique_suffix = uuid.uuid4().hex[:8]
            key = f"files/user_{request.user.id}/{timestamp}_{unique_suffix}_{clean_name}"
            saved_key = default_storage.save(key, uploaded_file)
            stored_keys.append(saved_key)

            FileItem.objects.update_or_create(
                s3Link=saved_key,
                defaults={
                    'name': clean_name,
                    'owner': request.user,
                    'parentFolder': parent_folder,
                    'isDeleted': False,
                },
            )

        payload['stored_keys'] = stored_keys

    logger.info('Files endpoint payload received: %s', payload)

    if uploaded_files:
        redirect_url = reverse('files')
        if parent_folder_id:
            redirect_url = f'{redirect_url}?folder={_encode_file_token(parent_folder_id)}'

        if request.headers.get('HX-Request') == 'true':
            response = HttpResponse()
            response['HX-Redirect'] = redirect_url
            return response

        message = f'Uploaded {len(uploaded_files)} file(s) and indexed them successfully.'
    else:
        message = f'Input for "{action}" received and logged.'

    return render(request, 'components/files/feedback_htmx.jinja', {
        'message': message,
    })


@login_required(login_url='login')
def files_download(request, item_token):
    if request.method != 'GET':
        return HttpResponse(status=405)

    item_id = _decode_file_token(item_token)
    if not item_id:
        return HttpResponse(status=404)

    item = FileItem.objects.filter(id=item_id, isDeleted=False, owner=request.user).first()
    if not item:
        return HttpResponse(status=404)

    if not item.s3Link or not default_storage.exists(item.s3Link):
        return HttpResponse(status=404)

    content_type = mimetypes.guess_type(item.name or '')[0] or 'application/octet-stream'
    file_handle = default_storage.open(item.s3Link, 'rb')
    return FileResponse(file_handle, as_attachment=True, filename=item.name, content_type=content_type)
