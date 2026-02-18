from django.http import HttpResponse, FileResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.urls import reverse
from django.core import signing
from django.core.signing import BadSignature
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models import Q

from ...models import FileItem, FileShare, User, UserType

import os
import mimetypes
import uuid
import logging

logger = logging.getLogger(__name__)
FILES_TOKEN_SALT = 'di4d-files-token'
FILES_USER_TOKEN_SALT = 'di4d-files-user-token'
FILES_SHARE_TARGET_TOKEN_SALT = 'di4d-files-share-target-token'


def _get_share_allowed_user_types():
    return list(UserType.objects.values('id', 'name'))


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


def _encode_user_token(user_id):
    return signing.dumps({'id': int(user_id)}, salt=FILES_USER_TOKEN_SALT)


def _decode_user_token(token):
    if not token:
        return None
    try:
        payload = signing.loads(token, salt=FILES_USER_TOKEN_SALT)
        user_id = payload.get('id')
        if not user_id:
            return None
        return int(user_id)
    except (BadSignature, ValueError, TypeError):
        return None


def _encode_share_target_token(target_type, value):
    return signing.dumps({'type': target_type, 'value': value}, salt=FILES_SHARE_TARGET_TOKEN_SALT)


def _decode_share_target_token(token):
    if not token:
        return None
    try:
        payload = signing.loads(token, salt=FILES_SHARE_TARGET_TOKEN_SALT)
        target_type = payload.get('type')
        value = payload.get('value')
        if target_type in ['user', 'usertype']:
            return {
                'type': target_type,
                'value': int(value),
            }
        return None
    except (BadSignature, ValueError, TypeError):
        return None


def _get_static_usertype_suggestions(query='', allowed_user_types=None):
    clean_query = (query or '').strip().lower()
    if allowed_user_types is None:
        allowed_user_types = _get_share_allowed_user_types()
    suggestions = []
    for user_type in allowed_user_types:
        readable_type = user_type['name'].replace('_', ' ')
        label = f"All {readable_type} users"
        if clean_query and clean_query not in readable_type and clean_query not in label.lower():
            continue
        suggestions.append({
            'label': label,
            'meta': f"User type: {readable_type}",
            'token': _encode_share_target_token('usertype', user_type['id']),
        })
    return suggestions


def _resolve_usertype_from_people_input(people_value, allowed_user_types=None):
    clean_people_value = (people_value or '').strip().lower()
    if not clean_people_value:
        return None

    if allowed_user_types is None:
        allowed_user_types = _get_share_allowed_user_types()

    for user_type in allowed_user_types:
        readable_type = user_type['name'].replace('_', ' ')
        supported_labels = {
            user_type['name'],
            readable_type,
            f"all {readable_type}",
            f"all {readable_type} users",
        }
        if clean_people_value in supported_labels:
            return user_type['id']
    return None


def _get_share_rows_context(file_item):
    shares = FileShare.objects.filter(fileItemId=file_item).select_related('userId', 'userTypeId').order_by('userId__firstname', 'userId__lastname', 'userId__username', 'userTypeId__name')
    share_rows = []
    for share in shares:
        if share.userId:
            shared_user = share.userId
            display_name = f"{(shared_user.firstname or '').strip()} {(shared_user.lastname or '').strip()}".strip() or shared_user.username
            share_rows.append({
                'display_name': display_name,
                'meta': f"username: {shared_user.username}",
                'target_token': _encode_share_target_token('user', shared_user.id),
                'can_edit': share.canEdit,
            })
        elif share.userTypeId:
            readable_type = (share.userTypeId.name or '').replace('_', ' ')
            share_rows.append({
                'display_name': f"All {readable_type} users",
                'meta': f"User type: {readable_type}",
                'target_token': _encode_share_target_token('usertype', share.userTypeId.id),
                'can_edit': share.canEdit,
            })
    return {
        'share_rows': share_rows,
    }


@login_required(login_url='login')
def files_view(request):
    active_page = 'files'
    view_mode = request.POST.get('view_mode', 'mine').strip().lower() if request.method == 'POST' else request.GET.get('view_mode', 'mine').strip().lower()
    if view_mode not in ['mine', 'shared']:
        view_mode = 'mine'

    search_query = request.POST.get('q', '').strip() if request.method == 'POST' else request.GET.get('q', '').strip()
    file_type = request.POST.get('file_type', 'all') if request.method == 'POST' else request.GET.get('file_type', 'all')
    current_folder_token = request.POST.get('folder') if request.method == 'POST' else request.GET.get('folder')
    current_folder_id = _decode_file_token(current_folder_token)
    current_folder = None
    parent_folder_token = None

    if view_mode == 'shared':
        current_folder_token = None
        current_folder_id = None

    if current_folder_id and view_mode == 'mine':
        current_folder = FileItem.objects.filter(id=current_folder_id, isDeleted=False, owner=request.user).select_related('parentFolder').first()
        if not current_folder:
            current_folder_token = None
            current_folder_id = None
        else:
            if current_folder.parentFolder:
                parent_folder_token = _encode_file_token(current_folder.parentFolder.id)

    if view_mode == 'shared':
        breadcrumbs = [{'label': 'Shared with you', 'token': ''}]
    else:
        breadcrumbs = [
            {
                'label': f'{request.user.username} (root)',
                'token': '',
            }
        ]

    if current_folder and view_mode == 'mine':
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

    if view_mode == 'shared':
        shared_filter = Q(shares__userId=request.user)
        if request.user.userTypeId_id:
            shared_filter |= Q(shares__userTypeId_id=request.user.userTypeId_id)

        db_items = FileItem.objects.filter(
            isDeleted=False,
        ).filter(
            shared_filter,
        ).exclude(owner=request.user).select_related('owner').distinct().order_by('-id')
    else:
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
            'can_manage': item.owner == request.user,
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
        'view_mode': view_mode,
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
    action = action.strip().lower()

    if action == 'share-list' and request.method == 'GET':
        item_token = request.GET.get('item_token')
        item_id = _decode_file_token(item_token)
        if not item_id:
            return HttpResponse(status=400)

        item = FileItem.objects.filter(id=item_id, isDeleted=False, owner=request.user).first()
        if not item:
            return HttpResponse(status=404)

        context = _get_share_rows_context(item)
        return render(request, 'components/files/share_rows_htmx.jinja', context)

    if request.method != 'POST':
        return HttpResponse(status=405)

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

    if action == 'share-suggest':
        query = (request.POST.get('people') or '').strip()
        item_token = request.POST.get('item_token')
        item_id = _decode_file_token(item_token)
        if not item_id:
            return render(request, 'components/files/share_suggestions_htmx.jinja', {'suggestions': []})

        item = FileItem.objects.filter(id=item_id, isDeleted=False, owner=request.user).first()
        if not item:
            return render(request, 'components/files/share_suggestions_htmx.jinja', {'suggestions': []})

        allowed_user_types = _get_share_allowed_user_types()
        suggestions = _get_static_usertype_suggestions(query, allowed_user_types=allowed_user_types)
        if query:
            allowed_user_type_names = [user_type['name'] for user_type in allowed_user_types]
            users = User.objects.filter(
                userTypeId__name__in=allowed_user_type_names,
                is_active=True,
            ).filter(
                Q(username__icontains=query)
                | Q(firstname__icontains=query)
                | Q(lastname__icontains=query)
                | Q(email__icontains=query)
            )[:8]

            for user in users:
                display_name = f"{(user.firstname or '').strip()} {(user.lastname or '').strip()}".strip() or user.username
                suggestions.append({
                    'label': display_name,
                    'meta': f"username: {user.username}",
                    'token': _encode_share_target_token('user', user.id),
                })

        return render(request, 'components/files/share_suggestions_htmx.jinja', {'suggestions': suggestions})

    if action == 'share':
        item_token = request.POST.get('item_token')
        item_id = _decode_file_token(item_token)
        if not item_id:
            return HttpResponse(status=400)

        item = FileItem.objects.filter(id=item_id, isDeleted=False, owner=request.user).first()
        if not item:
            return HttpResponse(status=404)

        share_mode = (request.POST.get('share_mode') or 'add').strip().lower()

        if share_mode == 'add':
            allowed_user_types = _get_share_allowed_user_types()
            allowed_user_type_ids = [user_type['id'] for user_type in allowed_user_types]
            allowed_user_type_names = [user_type['name'] for user_type in allowed_user_types]
            add_user_token = request.POST.get('add_user_token')
            share_target = _decode_share_target_token(add_user_token)
            if not share_target:
                add_user_id = _decode_user_token(add_user_token)
                if add_user_id:
                    share_target = {
                        'type': 'user',
                        'value': add_user_id,
                    }
            if not share_target:
                user_type_from_input = _resolve_usertype_from_people_input(
                    request.POST.get('people'),
                    allowed_user_types=allowed_user_types,
                )
                if user_type_from_input:
                    share_target = {
                        'type': 'usertype',
                        'value': user_type_from_input,
                    }
            rights = (request.POST.get('rights') or 'view_only').strip().lower()
            if share_target and share_target['type'] == 'user':
                user_to_share = User.objects.filter(
                    id=share_target['value'],
                    userTypeId__name__in=allowed_user_type_names,
                    is_active=True,
                ).first()
                if user_to_share:
                    FileShare.objects.update_or_create(
                        fileItemId=item,
                        userId=user_to_share,
                        userTypeId=None,
                        defaults={
                            'canEdit': rights == 'edit',
                        },
                    )
            elif share_target and share_target['type'] == 'usertype':
                user_type_id = share_target['value']
                if user_type_id in allowed_user_type_ids:
                    user_type = UserType.objects.filter(id=user_type_id).first()
                    if user_type:
                        FileShare.objects.update_or_create(
                            fileItemId=item,
                            userId=None,
                            userTypeId=user_type,
                            defaults={
                                'canEdit': rights == 'edit',
                            },
                        )

        elif share_mode == 'update':
            share_user_token = request.POST.get('share_user_token')
            share_target = _decode_share_target_token(share_user_token)
            if not share_target:
                share_user_id = _decode_user_token(share_user_token)
                if share_user_id:
                    share_target = {
                        'type': 'user',
                        'value': share_user_id,
                    }
            share_rights = (request.POST.get('share_rights') or 'view_only').strip().lower()
            if share_target and share_target['type'] == 'user':
                FileShare.objects.filter(fileItemId=item, userId_id=share_target['value']).update(canEdit=share_rights == 'edit')
            elif share_target and share_target['type'] == 'usertype':
                FileShare.objects.filter(fileItemId=item, userTypeId_id=share_target['value'], userId__isnull=True).update(canEdit=share_rights == 'edit')

        elif share_mode == 'remove':
            share_user_token = request.POST.get('share_user_token')
            share_target = _decode_share_target_token(share_user_token)
            if not share_target:
                share_user_id = _decode_user_token(share_user_token)
                if share_user_id:
                    share_target = {
                        'type': 'user',
                        'value': share_user_id,
                    }
            if share_target and share_target['type'] == 'user':
                FileShare.objects.filter(fileItemId=item, userId_id=share_target['value']).delete()
            elif share_target and share_target['type'] == 'usertype':
                FileShare.objects.filter(fileItemId=item, userTypeId_id=share_target['value'], userId__isnull=True).delete()

        context = _get_share_rows_context(item)
        return render(request, 'components/files/share_rows_htmx.jinja', context)

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

    item = FileItem.objects.filter(id=item_id, isDeleted=False).select_related('owner').first()
    if not item:
        return HttpResponse(status=404)

    can_access = item.owner == request.user or FileShare.objects.filter(
        Q(fileItemId=item, userId=request.user)
        | Q(fileItemId=item, userTypeId=request.user.userTypeId, userId__isnull=True)
    ).exists()
    if not can_access:
        return HttpResponse(status=403)

    if not item.s3Link or not default_storage.exists(item.s3Link):
        return HttpResponse(status=404)

    content_type = mimetypes.guess_type(item.name or '')[0] or 'application/octet-stream'
    file_handle = default_storage.open(item.s3Link, 'rb')
    return FileResponse(file_handle, as_attachment=True, filename=item.name, content_type=content_type)
