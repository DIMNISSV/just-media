# catalog/views.py
import json
from math import inf
from typing import Optional
from urllib.parse import urlparse, parse_qs
from django.db import models

# Import settings if not already imported
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
# Import Q for complex lookups, Exists, OuterRef
from django.db.models import Q, Prefetch, Exists, OuterRef
from django.http import JsonResponse, HttpResponseBadRequest  # Corrected import
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
# Removed csrf_exempt import and decorator
from django.views.generic import ListView, DetailView, View

from .forms import AdvancedMediaSearchForm
from .models import (
    MediaItem, MediaSourceLink, Season, Episode, ViewingHistory, Favorite,  # Added models needed
    # Ensure all models are imported if used below
)


class MediaItemListView(ListView):
    """ Displays a list of Media Items. """
    model = MediaItem
    template_name = 'catalog/mediaitem_list.html'
    context_object_name = 'media_items'
    paginate_by = 20

    def get_queryset(self):
        """Prefetches related data."""
        # Prefetch genres for card display
        return MediaItem.objects.prefetch_related('genres', 'countries').order_by('-updated_at', 'title')


class MediaItemDetailView(DetailView):
    """ Displays details for a single Media Item. """
    model = MediaItem
    template_name = 'catalog/mediaitem_detail.html'
    context_object_name = 'media_item'
    RELATED_ITEM_LIMIT = getattr(settings, 'CATALOG_RELATED_ITEM_LIMIT', 100)  # Max related items to show

    def get_queryset(self):
        """Prefetches related data and annotates favorite status."""
        queryset = MediaItem.objects.all()  # Use all() instead of super().get_queryset()

        if self.request.user.is_authenticated:
            is_favorite_subquery = Favorite.objects.filter(
                user=self.request.user,
                media_item=OuterRef('pk')
            )
            queryset = queryset.annotate(is_favorite=Exists(is_favorite_subquery))
        else:
            queryset = queryset.annotate(is_favorite=models.Value(False, output_field=models.BooleanField()))

        # Prefetching logic remains the same
        return queryset.prefetch_related(
            'genres',
            'countries',
            'source_metadata__source',
            Prefetch(
                'source_links',
                queryset=MediaSourceLink.objects.filter(episode__isnull=True).select_related('translation', 'source'),
                to_attr='main_source_links'
            ),
            Prefetch(
                'seasons',
                queryset=Season.objects.order_by('season_number').prefetch_related(
                    Prefetch(
                        'episodes',
                        queryset=Episode.objects.order_by('episode_number').prefetch_related(
                            'screenshots',
                            Prefetch(
                                'source_links',
                                queryset=MediaSourceLink.objects.select_related('translation', 'source')
                            )
                        ),
                        to_attr='prefetched_episodes'
                    )
                ),
                to_attr='prefetched_seasons'
            )
        )  # Removed .all() here, let DetailView handle the final get()

    def get_context_data(self, **kwargs):
        """Adds structured episode data, favorite status, and related items."""
        context = super().get_context_data(**kwargs)
        media_item: MediaItem = self.object  # Get the object from self.object
        episodes_data = {}
        main_links_data = {}

        # --- Populate episode/main links (no change) ---
        if hasattr(media_item, 'prefetched_seasons'):
            for season in media_item.prefetched_seasons:
                if hasattr(season, 'prefetched_episodes'):
                    for episode in season.prefetched_episodes:
                        episode_links = []
                        if hasattr(episode, 'source_links'):
                            for link in episode.source_links.all():
                                if link.translation:
                                    start_from = self._extract_start_from(link.player_link)
                                    episode_links.append({'translation_id': link.translation.kodik_id,
                                                          'translation_title': link.translation.title,
                                                          'link_pk': link.pk, 'quality': link.quality_info,
                                                          'start_from': start_from})
                        episode_links.sort(key=lambda x: x['translation_title'])
                        episodes_data[episode.pk] = episode_links
        if hasattr(media_item, 'main_source_links'):
            for link in media_item.main_source_links:
                if link.translation:
                    start_from = self._extract_start_from(link.player_link)
                    main_links_data[link.translation.kodik_id] = {'translation_id': link.translation.kodik_id,
                                                                  'link_pk': link.pk,
                                                                  'translation_title': link.translation.title,
                                                                  'quality': link.quality_info,
                                                                  'start_from': start_from}
        # --- End populate links ---

        context['episodes_links_json'] = json.dumps(episodes_data)
        context['main_links_json'] = json.dumps(main_links_data)
        context['has_main_links'] = bool(main_links_data)
        context['is_favorite'] = getattr(media_item, 'is_favorite', False)

        # --- Find Related Items ---
        related_items_qs = MediaItem.objects.none()
        # Build Q object based on *non-empty* IDs of the current item
        related_q = Q()
        has_relation_id = False
        if media_item.kinopoisk_id:
            related_q |= Q(kinopoisk_id=media_item.kinopoisk_id)
            has_relation_id = True
        if media_item.imdb_id:
            related_q |= Q(imdb_id=media_item.imdb_id)
            has_relation_id = True
        if media_item.shikimori_id:
            related_q |= Q(shikimori_id=media_item.shikimori_id)
            # Maybe don't set has_relation_id for non-global IDs? Optional.
            # has_relation_id = True
        if media_item.mydramalist_id:
            related_q |= Q(mydramalist_id=media_item.mydramalist_id)
            # has_relation_id = True

        if has_relation_id:  # Only search if we have KP or IMDb ID
            related_items_qs = MediaItem.objects.filter(related_q).exclude(
                pk=media_item.pk  # Exclude self
            ).prefetch_related(
                'genres'  # Prefetch genres for related item cards
            ).order_by(
                '-release_year', '-updated_at'  # Order by relevance (newest first)
            )[:self.RELATED_ITEM_LIMIT]  # Apply limit

        context['related_items'] = related_items_qs
        # --- End Find Related Items ---

        # --- JS Translations (no change) ---
        js_trans_dict = {
            'error_loading_player': str(_("Error loading player.")),
            'no_content_available': str(_("No content available.")),
            'select_translation': str(_("Select a translation to start watching")),
            'select_episode': str(_("Select an episode to start watching")),
            'select_episode_or_translation': str(_("Select an episode or translation to start watching")),
            'no_translations_for_episode': str(_("No translations found for this episode.")),
            'player_only_unavailable': str(_("Player only option unavailable (no main item link found)")),
            'player_only_enabled': str(_("Player only (hide episodes)")),
            'add_to_favorites': str(_("Add to Favorites")), 'remove_from_favorites': str(_("Remove from Favorites")),
            'toggling_favorite': str(_("Working...")), 'toggle_favorite_error': str(_("Error updating favorites.")),
        }
        context['js_translations'] = json.dumps(js_trans_dict)
        return context

    def _extract_start_from(self, player_link: str) -> Optional[int]:
        """Extracts 'start_from' parameter."""
        # ... (implementation remains the same) ...
        if not player_link: return None
        try:
            effective_link = player_link
            if player_link.startswith("//"): effective_link = "http:" + player_link
            parsed_url = urlparse(effective_link)
            query_params = parse_qs(parsed_url.query)
            start_from_list = query_params.get('start_from')
            if start_from_list: return int(start_from_list[0])
        except (ValueError, TypeError, IndexError):
            pass
        return None


# --- PlaySourceLinkView, MediaItemSearchView, TrackWatchView, ToggleFavoriteView - без изменений ---
class PlaySourceLinkView(DetailView):
    model = MediaSourceLink
    template_name = 'catalog/play_source_link.html'
    context_object_name = 'source_link'

    def get_queryset(self):
        return MediaSourceLink.objects.select_related('source', 'translation', 'episode__season__media_item',
                                                      'media_item').all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source_link_obj = context['source_link']
        start_from = self._extract_start_from(source_link_obj.player_link)
        player_url = source_link_obj.player_link
        if start_from is not None and player_url:
            if f'start_from={start_from}' not in player_url:
                try:
                    effective_link = player_url
                    if player_url.startswith("//"): effective_link = "http:" + player_url
                    parsed = urlparse(effective_link)
                    query_params = parse_qs(parsed.query)
                    if 'start_from' not in query_params:
                        separator = '&' if parsed.query else '?'
                        player_url += f"{separator}start_from={start_from}"
                except Exception:
                    pass
        context['player_url_with_start'] = player_url
        return context

    def _extract_start_from(self, player_link: str) -> Optional[int]:
        if not player_link: return None
        try:
            effective_link = player_link
            if player_link.startswith("//"): effective_link = "http:" + player_link
            parsed_url = urlparse(effective_link)
            query_params = parse_qs(parsed_url.query)
            start_from_list = query_params.get('start_from')
            if start_from_list: return int(start_from_list[0])
        except (ValueError, TypeError, IndexError):
            pass
        return None


class MediaItemSearchView(ListView):
    model = MediaItem
    template_name = 'catalog/mediaitem_search_results.html'
    context_object_name = 'search_results'
    paginate_by = 20

    def get_queryset(self):
        queryset = MediaItem.objects.prefetch_related('genres', 'countries').order_by('-updated_at', 'title')
        form = AdvancedMediaSearchForm(self.request.GET)
        if form.is_valid():
            query = form.cleaned_data.get('q')
            year_from = form.cleaned_data.get('year_from')
            year_to = form.cleaned_data.get('year_to')
            media_type = form.cleaned_data.get('media_type')
            genres = form.cleaned_data.get('genres')
            if query: queryset = queryset.filter(Q(title__icontains=query) | Q(original_title__icontains=query))
            if year_from: queryset = queryset.filter(release_year__gte=year_from)
            if year_to: queryset = queryset.filter(release_year__lte=year_to)
            if media_type: queryset = queryset.filter(media_type=media_type)
            if genres: queryset = queryset.filter(genres__in=genres).distinct()
        else:
            if form.errors: queryset = MediaItem.objects.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = AdvancedMediaSearchForm(self.request.GET or None)
        context['query_params'] = self.request.GET.urlencode()
        return context


class TrackWatchView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        link_pk = request.POST.get('link_pk')
        if not link_pk: return HttpResponseBadRequest("Missing 'link_pk' parameter.")
        try:
            link_pk = int(link_pk)
        except (ValueError, TypeError):
            return HttpResponseBadRequest("Invalid 'link_pk' parameter.")
        source_link = get_object_or_404(MediaSourceLink.objects.select_related('episode'), pk=link_pk)
        defaults = {'episode': source_link.episode}
        try:
            history_entry, created = ViewingHistory.objects.update_or_create(user=request.user, link=source_link,
                                                                             defaults=defaults)
            action = "created" if created else "updated"
            print(
                f"Viewing history {action} for user {request.user.username}, link {link_pk}, episode {source_link.episode}")
            return JsonResponse({'status': 'success', 'action': action})
        except Exception as e:
            print(f"Error saving viewing history: {e}")
            return JsonResponse(
                {'status': 'error', 'message': 'Internal server error'}, status=500)

    def handle_no_permission(self):
        return JsonResponse({'status': 'error', 'message': 'Login required.'}, status=403)  # Changed to JsonResponse


class ToggleFavoriteView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        media_item_pk = request.POST.get('media_item_pk')
        if not media_item_pk: return JsonResponse({'status': 'error', 'message': "Missing 'media_item_pk'."},
                                                  status=400)
        try:
            media_item_pk = int(media_item_pk)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': "Invalid 'media_item_pk'."}, status=400)
        media_item = get_object_or_404(MediaItem, pk=media_item_pk)
        action = None
        is_favorite_now = False
        try:
            favorite, created = Favorite.objects.get_or_create(user=request.user, media_item=media_item)
            if created:
                action = 'added'
                is_favorite_now = True
                print(
                    f"Favorite added for user {request.user.username}, item {media_item_pk}")
            else:
                favorite.delete()
                action = 'removed'
                is_favorite_now = False
                print(
                    f"Favorite removed for user {request.user.username}, item {media_item_pk}")
            return JsonResponse({'status': 'success', 'action': action, 'is_favorite': is_favorite_now})
        except Exception as e:
            print(
                f"Error toggling favorite for user {request.user.username}, item {media_item_pk}: {e}")
            return JsonResponse(
                {'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)

    def handle_no_permission(self):
        return JsonResponse({'status': 'error', 'message': 'Login required.'}, status=403)
