// catalog/static/catalog/js/media_detail_handler.js
document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const playerPlaceholder = document.getElementById('player-placeholder');
    const episodesContainer = document.getElementById('seasons-tab-content');
    const nextEpisodeBtn = document.getElementById('next-episode-btn');
    const prevEpisodeBtn = document.getElementById('prev-episode-btn');
    const playerUrlTemplateEl = document.getElementById('player-url-template');
    // Translation elements
    const translationSelectorPlaceholder = document.getElementById('translation-selector-placeholder');
    const translationLabel = translationSelectorPlaceholder?.querySelector('.translation-label');
    const translationButtonsContainer = document.getElementById('translation-buttons-container');
    const noTranslationsMessage = document.getElementById('no-translations-message');
    // ---
    const episodesLinksDataElement = document.getElementById('episodes-links-data');
    const mainLinksDataElement = document.getElementById('main-links-data');
    const jsTranslationsElement = document.getElementById('js-translations-data'); // Get translations
    const trackHistoryUrlElement = document.getElementById('track-watch-history-url'); // Get URL from template
    const userAuthStatusElement = document.getElementById('user-auth-status'); // Get auth status
    const csrfTokenInput = document.querySelector('#watch-pane input[name="csrfmiddlewaretoken"]'); // Get CSRF from watch pane

    const mediaPk = document.getElementById('seasons-tab-content')?.dataset.mediaPk;
    const watchAreaRow = document.getElementById('watch-area-row');
    const playerContainerColumn = document.getElementById('player-container-column');
    const episodeListColumn = document.getElementById('episodes-container-column');
    const layoutRadios = document.querySelectorAll('input[name="playerLayout"]');
    const playerOnlyRadio = document.getElementById('layoutPlayerOnly');
    const playerOnlyLabel = document.querySelector('label[for="layoutPlayerOnly"]');

    // --- State Variables ---
    let currentEpisodeElement = null;
    let currentSelectedTranslationId = null;
    let episodesLinksData = {};
    let mainLinksData = {};
    let jsTranslations = {}; // Store JS translations
    let currentLayout = 'episodes_below';
    let isUserAuthenticated = false;
    let trackHistoryUrl = null;
    let csrfToken = null;

    // --- Constants ---
    const LAST_EPISODE_KEY = mediaPk ? `last_watched_episode_${mediaPk}` : null;
    const LAST_TRANSLATION_KEY = mediaPk ? `last_selected_translation_${mediaPk}` : null;
    const LAST_DETAIL_TAB_KEY = mediaPk ? `last_detail_tab_${mediaPk}` : null;
    const PLAYER_LAYOUT_KEY = `player_layout_preference`;
    const PLAYER_URL_TEMPLATE = playerUrlTemplateEl?.dataset.url;
    const LAYOUTS = ['episodes_below', 'episodes_right', 'player_only'];
    const SCROLL_CLASS = 'episodes-sidebar-scroll';
    const LIST_VIEW_CLASS = 'episodes-list-view';

    // --- Utility Functions ---
    function parseJsonData(element, description) {
        if (!element) {
            console.warn(`${description} data element not found.`);
            return {};
        }
        try {
            return JSON.parse(element.textContent || '{}');
        } catch (e) {
            console.error(`Error parsing ${description} data:`, e);
            return {};
        }
    }

    function generatePlayerUrl(linkPk) {
        if (!PLAYER_URL_TEMPLATE || !linkPk) return null;
        return PLAYER_URL_TEMPLATE.replace(/(\/play\/)\d+(\/)/, `$1${linkPk}$2`);
    }

    function getStartFromValue(linkData) {
        return linkData?.start_from ?? null;
    }

    // --- Placeholder Text Function ---
    function setPlaceholderText(textKey) {
        if (playerPlaceholder) {
            const text = jsTranslations[textKey] || "Loading..."; // Fallback text
            playerPlaceholder.innerHTML = `<div class="text-center text-muted border rounded p-5">${text}</div>`;
        }
    }

    // --- Function to track watch history ---
    function trackWatchHistory(linkPk) {
        if (!isUserAuthenticated) {
            console.log("History tracking skipped: User not authenticated.");
            return; // Don't track for anonymous users
        }
        if (!trackHistoryUrl) {
            console.warn("History tracking skipped: Tracking URL not found in template.");
            return;
        }
        if (!csrfToken) {
            console.error("History tracking failed: CSRF token not found.");
            return; // Can't make POST without CSRF
        }
        if (!linkPk) {
            console.warn("History tracking skipped: Invalid link PK.");
            return;
        }

        console.log(`Tracking watch history for link PK: ${linkPk}`);

        const formData = new FormData();
        formData.append('link_pk', linkPk);

        fetch(trackHistoryUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest', // Optional: Mark as AJAX
            },
            body: formData
        })
            .then(response => {
                if (!response.ok) {
                    // Throw error to be caught below
                    throw new Error(`HTTP error! status: ${response.status} - ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    console.log(`Watch history ${data.action} successfully for link PK: ${linkPk}`);
                } else {
                    console.warn(`History tracking backend response indicates failure for link PK ${linkPk}:`, data);
                }
            })
            .catch(error => {
                console.error(`Error tracking watch history for link PK ${linkPk}:`, error);
            });
    }

    // --- Core Logic Functions ---
    function loadPlayer(linkPk, translationIdToSave, startFrom = null) {
        const playerUrl = generatePlayerUrl(linkPk);
        console.log(`Attempting to load player for link PK: ${linkPk}, Translation ID: ${translationIdToSave}, URL: ${playerUrl}, StartFrom: ${startFrom}`);
        if (playerUrl && playerPlaceholder) {
            playerPlaceholder.innerHTML = `<div class="player-container"><iframe src="${playerUrl}" allowfullscreen="allowfullscreen" webkitallowfullscreen="webkitallowfullscreen" mozallowfullscreen="mozallowfullscreen" loading="eager"></iframe></div>`;

            // --- Call history tracking ---
            trackWatchHistory(linkPk);
            // -----------------------------

            if (LAST_TRANSLATION_KEY && translationIdToSave) {
                localStorage.setItem(LAST_TRANSLATION_KEY, translationIdToSave);
                currentSelectedTranslationId = translationIdToSave.toString();
                console.log(`Saved last translation ID: ${currentSelectedTranslationId}`);
            }
            if (currentEpisodeElement && LAST_EPISODE_KEY && currentLayout !== 'player_only') {
                const episodePk = currentEpisodeElement.dataset.episodePk;
                localStorage.setItem(LAST_EPISODE_KEY, episodePk);
                console.log(`Saved last episode PK: ${episodePk}`);
            } else if (!currentEpisodeElement && LAST_EPISODE_KEY && currentLayout === 'player_only') {
                console.log("In player_only mode, keeping last episode PK if previously set.");
            }

            const iframe = playerPlaceholder.querySelector('iframe');
            if (iframe) {
                iframe.onload = () => {
                    try {
                        const message = {type: 'playerInfo', startFrom: startFrom};
                        iframe.contentWindow.postMessage(message, '*');
                    } catch (e) {
                        console.warn("Could not post message to iframe.", e);
                    }
                };
            }
        } else {
            console.error('Could not generate player URL or player placeholder not found.');
            setPlaceholderText('error_loading_player');
        }
    }

    function displayTranslationOptions(episodePk, preferredTranslationId = null) {
        if (!translationButtonsContainer || !translationLabel || !noTranslationsMessage) {
            console.error("Translation UI elements not found!");
            return null;
        }

        let links = [];
        let isMainLinkContext = (currentLayout === 'player_only');

        if (isMainLinkContext) {
            links = Object.values(mainLinksData);
            links.sort((a, b) => a.translation_title.localeCompare(b.translation_title));
            console.log(`Displaying translations for MAIN ITEM using ${links.length} main links.`);
        } else if (episodePk && episodesLinksData[episodePk]) {
            links = episodesLinksData[episodePk];
            console.log(`Displaying translations for EPISODE ${episodePk} using ${links.length} episode links.`);
        } else {
            console.log(`No links found for context. Layout: ${currentLayout}, Episode PK: ${episodePk}`);
        }

        translationButtonsContainer.innerHTML = '';
        translationLabel.style.display = 'none';
        noTranslationsMessage.style.display = 'none';

        let translationLinkToAutoLoad = null;

        if (links.length > 0) {
            translationLabel.style.display = '';

            let preferredLink = null;
            const preferredIdStr = preferredTranslationId?.toString();
            if (preferredIdStr) {
                preferredLink = links.find(link => link.translation_id?.toString() === preferredIdStr);
                console.log(`Preferred translation ID ${preferredIdStr} found in links: ${!!preferredLink}`);
            }

            translationLinkToAutoLoad = preferredLink || links[0];
            console.log(`Auto-loading translation: ${translationLinkToAutoLoad?.translation_title} (PK: ${translationLinkToAutoLoad?.link_pk})`);

            let buttonsHtml = '';
            links.forEach(link => {
                const quality = link.quality ? ` (${link.quality})` : '';
                const isSelected = translationLinkToAutoLoad && link.link_pk === translationLinkToAutoLoad.link_pk;
                const btnClass = isSelected ? 'btn-primary active' : 'btn-outline-primary';
                const startFromAttr = link.start_from ? `data-start-from="${link.start_from}"` : '';
                buttonsHtml += `<button class="btn btn-sm ${btnClass} me-1 mb-1 translation-btn"
                                       data-link-pk="${link.link_pk}"
                                       data-translation-id="${link.translation_id}"
                                       ${startFromAttr}>
                                    ${link.translation_title}${quality}
                                </button>`;
            });
            translationButtonsContainer.innerHTML = buttonsHtml;

            return translationLinkToAutoLoad;

        } else {
            noTranslationsMessage.textContent = jsTranslations['no_translations_for_episode'] || "No translations available."; // Set text content
            noTranslationsMessage.style.display = '';
            setPlaceholderText('no_content_available');
            return null;
        }
    }

    function highlightEpisode(episodeElement) {
        document.querySelectorAll('#seasons-tab-content .episode-selector.active').forEach(el => {
            el.classList.remove('active', 'border', 'border-primary', 'border-3');
        });

        if (episodeElement) {
            episodeElement.classList.add('active', 'border', 'border-primary', 'border-3');
            currentEpisodeElement = episodeElement;

            if (episodeListColumn?.classList.contains(SCROLL_CLASS)) {
                episodeElement.scrollIntoView({behavior: 'smooth', block: 'nearest'});
            }
        } else {
            currentEpisodeElement = null;
        }
        updateNavButtons();
    }


    function highlightTranslationButton(buttonElement) {
        translationButtonsContainer?.querySelectorAll('.translation-btn.active').forEach(btn => {
            btn.classList.remove('active', 'btn-primary');
            btn.classList.add('btn-outline-primary');
        });
        if (buttonElement) {
            buttonElement.classList.remove('btn-outline-primary');
            buttonElement.classList.add('active', 'btn-primary');
        }
    }

    function findEpisodeElementByPk(episodePk) {
        if (!episodesContainer || !episodePk) return null;
        return episodesContainer.querySelector(`.episode-selector[data-episode-pk='${episodePk}']`);
    }

    function findNextEpisodeElement(currentElement) {
        if (!currentElement) return null;
        const currentEpisodePk = currentElement.dataset.episodePk;
        const parentCol = currentElement.closest('.col');
        if (!parentCol) {
            console.warn(`[findNext] Could not find parent .col for episode PK ${currentEpisodePk}`);
            return null;
        }
        let nextElement = null;
        let nextCol = parentCol.nextElementSibling;
        while (nextCol && !nextCol.querySelector('.episode-selector')) {
            nextCol = nextCol.nextElementSibling;
        }
        if (nextCol) {
            nextElement = nextCol.querySelector('.episode-selector');
            console.log(`[findNext] Found next element PK ${nextElement?.dataset.episodePk} in next column.`);
        } else {
            console.log(`[findNext] No next sibling column found for episode PK ${currentEpisodePk}. Checking next season.`);
            const currentTabPane = currentElement.closest('.tab-pane');
            if (!currentTabPane) return null;
            const nextTabPane = currentTabPane.nextElementSibling;
            if (nextTabPane?.classList.contains('tab-pane')) {
                const nextTabButton = document.getElementById(nextTabPane.getAttribute('aria-labelledby'));
                if (nextTabButton) {
                    try {
                        new bootstrap.Tab(nextTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap tab error:", e)
                    }
                }
                nextElement = nextTabPane.querySelector('.episode-selector');
                console.log(`[findNext] Switched to next season tab. First episode: ${nextElement?.dataset.episodePk}`);
            } else {
                console.log("[findNext] No next season tab found.");
            }
        }
        return nextElement;
    }

    function findPrevEpisodeElement(currentElement) {
        if (!currentElement) return null;
        const currentEpisodePk = currentElement.dataset.episodePk;
        const parentCol = currentElement.closest('.col');
        if (!parentCol) {
            console.warn(`[findPrev] Could not find parent .col for episode PK ${currentEpisodePk}`);
            return null;
        }
        let prevElement = null;
        let prevCol = parentCol.previousElementSibling;
        while (prevCol && !prevCol.querySelector('.episode-selector')) {
            prevCol = prevCol.previousElementSibling;
        }
        if (prevCol) {
            prevElement = prevCol.querySelector('.episode-selector');
            console.log(`[findPrev] Found previous element PK ${prevElement?.dataset.episodePk} in previous column.`);
        } else {
            console.log(`[findPrev] No previous sibling column found for episode PK ${currentEpisodePk}. Checking previous season.`);
            const currentTabPane = currentElement.closest('.tab-pane');
            if (!currentTabPane) return null;
            const prevTabPane = currentTabPane.previousElementSibling;
            if (prevTabPane?.classList.contains('tab-pane')) {
                const prevTabButton = document.getElementById(prevTabPane.getAttribute('aria-labelledby'));
                if (prevTabButton) {
                    try {
                        new bootstrap.Tab(prevTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap tab error:", e)
                    }
                }
                const episodes = prevTabPane.querySelectorAll('.episode-selector');
                prevElement = episodes.length > 0 ? episodes[episodes.length - 1] : null;
                console.log(`[findPrev] Switched to previous season tab. Last episode: ${prevElement?.dataset.episodePk}`);
            } else {
                console.log("[findPrev] No previous season tab found.");
            }
        }
        return prevElement;
    }


    function updateNavButtons() {
        const nextElement = findNextEpisodeElement(currentEpisodeElement);
        const prevElement = findPrevEpisodeElement(currentEpisodeElement);
        const navContainer = episodeListColumn?.querySelector('.d-flex.justify-content-between.align-items-center');
        if (navContainer) {
            navContainer.style.display = (currentLayout === 'player_only') ? 'none' : '';
        }
        if (nextEpisodeBtn) nextEpisodeBtn.disabled = !nextElement || currentLayout === 'player_only';
        if (prevEpisodeBtn) prevEpisodeBtn.disabled = !prevElement || currentLayout === 'player_only';
    }


    function handleEpisodeSelection(episodeElement, manuallyClicked = false) {
        if (!episodeElement || currentLayout === 'player_only') {
            console.log("Episode selection ignored. Element:", episodeElement, "Layout:", currentLayout);
            return;
        }
        const episodePk = episodeElement.dataset.episodePk;
        console.log(`Handling episode selection for PK: ${episodePk}, Manual Click: ${manuallyClicked}`);
        highlightEpisode(episodeElement);
        const preferredTranslationId = LAST_TRANSLATION_KEY ? localStorage.getItem(LAST_TRANSLATION_KEY) : currentSelectedTranslationId;
        console.log(`Preferred Translation ID for episode selection: ${preferredTranslationId}`);
        const translationLinkToLoad = displayTranslationOptions(episodePk, preferredTranslationId);

        if (translationLinkToLoad) {
            const startFrom = getStartFromValue(translationLinkToLoad);
            loadPlayer(translationLinkToLoad.link_pk, translationLinkToLoad.translation_id.toString(), startFrom);
            const translationButton = translationButtonsContainer?.querySelector(`.translation-btn[data-link-pk='${translationLinkToLoad.link_pk}']`);
            highlightTranslationButton(translationButton);
        } else {
            console.log(`No translation link to load for episode PK ${episodePk}`);
            setPlaceholderText('no_translations_for_episode');
            currentSelectedTranslationId = null;
            highlightTranslationButton(null);
        }

        const watchTabButton = document.getElementById('watch-tab');
        if (manuallyClicked && watchTabButton && !watchTabButton.classList.contains('active')) {
            try {
                new bootstrap.Tab(watchTabButton).show();
            } catch (e) {
                console.error("Bootstrap tab error:", e)
            }
        }
    }


    function restoreLastWatchedState() {
        if (currentLayout === 'player_only') {
            console.log("Restore Watched State: In player_only layout.");
            const preferredTranslationId = LAST_TRANSLATION_KEY ? localStorage.getItem(LAST_TRANSLATION_KEY) : null;
            const mainTranslationLink = displayTranslationOptions(null, preferredTranslationId);
            if (mainTranslationLink) {
                const startFrom = getStartFromValue(mainTranslationLink);
                loadPlayer(mainTranslationLink.link_pk, mainTranslationLink.translation_id.toString(), startFrom);
                const mainTranslationButton = translationButtonsContainer?.querySelector(`.translation-btn[data-link-pk='${mainTranslationLink.link_pk}']`);
                highlightTranslationButton(mainTranslationButton);
            } else {
                setPlaceholderText('select_translation');
                highlightTranslationButton(null);
            }
            return;
        }

        console.log("Restore Watched State: Checking for last episode...");
        if (!LAST_EPISODE_KEY) {
            console.log("Restore Watched State: No episode key defined.");
            setPlaceholderText('select_episode_or_translation');
            return;
        }

        const lastEpisodePk = localStorage.getItem(LAST_EPISODE_KEY);
        if (lastEpisodePk) {
            const lastEpisodeElement = findEpisodeElementByPk(lastEpisodePk);
            if (lastEpisodeElement) {
                console.log(`Restore Watched State: Restoring last watched episode: PK ${lastEpisodePk}`);
                const targetTabPaneId = lastEpisodeElement.closest('.tab-pane')?.id;
                const targetSeasonButton = targetTabPaneId ? document.querySelector(`button[data-bs-target='#${targetTabPaneId}']`) : null;

                if (targetSeasonButton && !targetSeasonButton.classList.contains('active')) {
                    console.log(`Restore Watched State: Activating season tab for episode ${lastEpisodePk}`);
                    try {
                        targetSeasonButton.addEventListener('shown.bs.tab', () => {
                            console.log(`Restore Watched State: Tab shown for ${targetTabPaneId}, selecting episode.`);
                            handleEpisodeSelection(lastEpisodeElement, false);
                        }, {once: true});
                        new bootstrap.Tab(targetSeasonButton).show();
                    } catch (e) {
                        console.error("Bootstrap tab error during restore:", e);
                        handleEpisodeSelection(lastEpisodeElement, false);
                    }
                } else {
                    console.log(`Restore Watched State: Correct tab already active or button not found, selecting episode.`);
                    handleEpisodeSelection(lastEpisodeElement, false);
                }
            } else {
                console.log(`Restore Watched State: Could not find last watched episode element (PK ${lastEpisodePk}) in DOM.`);
                setPlaceholderText('select_episode');
                displayTranslationOptions(null, null);
                highlightEpisode(null);
            }
        } else {
            console.log("Restore Watched State: No last watched episode found in localStorage.");
            setPlaceholderText('select_episode');
            displayTranslationOptions(null, null);
            highlightEpisode(null);
        }
    }


    function restoreLastDetailTab() {
        if (!LAST_DETAIL_TAB_KEY) return;
        const lastTabTarget = localStorage.getItem(LAST_DETAIL_TAB_KEY);
        const defaultTabSelector = '#details-pane';
        const targetSelector = lastTabTarget || defaultTabSelector;
        const tabButton = document.querySelector(`#detail-tabs button[data-bs-target="${targetSelector}"]`);

        if (tabButton && !tabButton.classList.contains('active')) {
            try {
                console.log(`Restoring detail tab: ${targetSelector}`);
                new bootstrap.Tab(tabButton).show();
            } catch (e) {
                console.error("Bootstrap Tab error on restore:", e);
            }
        } else if (!tabButton) {
            console.warn(`Could not find button for stored tab selector: ${targetSelector}. Falling back to default.`);
            const defaultTabButton = document.querySelector(`#detail-tabs button[data-bs-target="${defaultTabSelector}"]`);
            if (defaultTabButton && !defaultTabButton.classList.contains('active')) {
                try {
                    new bootstrap.Tab(defaultTabButton).show();
                } catch (e) {
                }
            }
        }
    }


    function applyLayoutPreference(layout, triggeredByInitialization = false) {
        console.log(`ApplyLayoutPreference called with layout: '${layout}', Initializing: ${triggeredByInitialization}`);
        if (!playerContainerColumn || !episodeListColumn || !watchAreaRow) {
            console.error("Layout columns or row not found in DOM!");
            return;
        }
        const chosenLayout = LAYOUTS.includes(layout) ? layout : 'episodes_below';
        console.log(`Chosen layout: '${chosenLayout}'`);
        if (currentLayout === chosenLayout && !triggeredByInitialization) {
            console.log(`Layout '${chosenLayout}' is already active. Skipping redundant application.`);
            return;
        }
        const previousLayout = currentLayout;
        currentLayout = chosenLayout;

        let playerColClasses = ['col-12'];
        let episodeColClasses = ['col-12'];
        let episodeHidden = false;
        let addScrollClass = false;
        let addListViewClass = false;
        let episodeMargin = 'mt-3';

        switch (chosenLayout) {
            case 'episodes_right':
                playerColClasses = ['col-lg-9', 'col-md-12'];
                episodeColClasses = ['col-lg-3', 'col-md-12'];
                addScrollClass = true;
                addListViewClass = true;
                episodeMargin = 'mt-3 mt-lg-0';
                break;
            case 'player_only':
                playerColClasses = ['col-12'];
                episodeHidden = true;
                episodeMargin = '';
                break;
            case 'episodes_below':
                episodeMargin = 'mt-3 mb-3';
                break;
        }
        console.log(`Applying classes - Player: ${playerColClasses.join(' ')}, Episodes: ${episodeColClasses.join(' ')}, Hidden: ${episodeHidden}, Scroll: ${addScrollClass}, ListView: ${addListViewClass}, MarginTop: '${episodeMargin}'`);

        playerContainerColumn.className = '';
        episodeListColumn.className = '';
        playerContainerColumn.classList.add('col-12', ...playerColClasses);
        episodeListColumn.classList.add('col-12', ...episodeColClasses);

        if (episodeHidden) {
            episodeListColumn.classList.add('d-none');
        } else {
            episodeListColumn.classList.remove('d-none');
            if (episodeMargin) {
                episodeMargin.split(' ').forEach(cls => episodeListColumn.classList.add(cls));
            }
        }
        if (addScrollClass) {
            episodeListColumn.classList.add(SCROLL_CLASS);
        } else {
            episodeListColumn.classList.remove(SCROLL_CLASS);
        }
        if (addListViewClass) {
            episodeListColumn.classList.add(LIST_VIEW_CLASS);
        } else {
            episodeListColumn.classList.remove(LIST_VIEW_CLASS);
        }

        localStorage.setItem(PLAYER_LAYOUT_KEY, chosenLayout);
        console.log(`Saved preference to localStorage: ${chosenLayout}`);
        layoutRadios.forEach(radio => {
            radio.checked = (radio.value === chosenLayout);
        });
        updateNavButtons();

        if (previousLayout !== chosenLayout) {
            console.log(`Layout changed from '${previousLayout}' to '${chosenLayout}'`);
            if (chosenLayout === 'player_only') {
                console.log("Transitioning to player_only mode...");
                highlightEpisode(null);
                const preferredTranslationId = currentSelectedTranslationId || (LAST_TRANSLATION_KEY ? localStorage.getItem(LAST_TRANSLATION_KEY) : null);
                const mainTranslationLink = displayTranslationOptions(null, preferredTranslationId);
                if (mainTranslationLink) {
                    const startFrom = getStartFromValue(mainTranslationLink);
                    loadPlayer(mainTranslationLink.link_pk, mainTranslationLink.translation_id.toString(), startFrom);
                    const mainTranslationButton = translationButtonsContainer?.querySelector(`.translation-btn[data-link-pk='${mainTranslationLink.link_pk}']`);
                    highlightTranslationButton(mainTranslationButton);
                } else {
                    setPlaceholderText('select_translation');
                    highlightTranslationButton(null);
                }
            } else if (previousLayout === 'player_only') {
                console.log("Transitioning from player_only mode...");
                const lastEpisodePk = LAST_EPISODE_KEY ? localStorage.getItem(LAST_EPISODE_KEY) : null;
                const lastEpisodeElement = lastEpisodePk ? findEpisodeElementByPk(lastEpisodePk) : null;
                if (lastEpisodeElement) {
                    handleEpisodeSelection(lastEpisodeElement, false);
                } else {
                    setPlaceholderText('select_episode');
                    displayTranslationOptions(null, null);
                    highlightEpisode(null);
                    highlightTranslationButton(null);
                }
            } else {
                if (currentEpisodeElement) {
                    highlightEpisode(currentEpisodeElement);
                } else {
                    displayTranslationOptions(null, null);
                }
            }
        } else {
            console.log(`Layout '${chosenLayout}' was already set, no transition logic needed.`);
        }
    }


    function initializeLayout() {
        console.log("Initializing layout...");
        const storedLayout = localStorage.getItem(PLAYER_LAYOUT_KEY);
        console.log("Stored layout from localStorage:", storedLayout);
        let layoutToApply = storedLayout || 'episodes_below';
        if (layoutToApply === 'player_only' && playerOnlyRadio?.disabled) {
            layoutToApply = 'episodes_below';
            console.log("Player_only layout disabled, falling back to episodes_below for initialization.");
        }
        console.log("Layout to apply on initialization:", layoutToApply);
        applyLayoutPreference(layoutToApply, true);
    }


    function checkPlayerOnlyAvailability() {
        const hasMainLinks = Object.keys(mainLinksData).length > 0;
        if (playerOnlyRadio && playerOnlyLabel) {
            if (!hasMainLinks) {
                console.log("Disabling player_only layout option: No main links found.");
                playerOnlyRadio.disabled = true;
                playerOnlyLabel.classList.add('disabled', 'opacity-50');
                playerOnlyLabel.setAttribute('title', jsTranslations['player_only_unavailable'] || 'Player only unavailable');
            } else {
                playerOnlyRadio.disabled = false;
                playerOnlyLabel.classList.remove('disabled', 'opacity-50');
                playerOnlyLabel.setAttribute('title', jsTranslations['player_only_enabled'] || 'Player only');
            }
        }
    }


    // --- Event Listeners ---
    if (episodesContainer) {
        episodesContainer.addEventListener('click', (event) => {
            const episodeCard = event.target.closest('.episode-selector');
            if (episodeCard && currentLayout !== 'player_only') {
                event.preventDefault();
                handleEpisodeSelection(episodeCard, true);
            }
        });
    }

    if (translationButtonsContainer) {
        translationButtonsContainer.addEventListener('click', (event) => {
            const translationButton = event.target.closest('.translation-btn');
            if (translationButton) {
                event.preventDefault();
                const linkPk = translationButton.dataset.linkPk;
                const translationId = translationButton.dataset.translationId;
                const startFrom = parseInt(translationButton.dataset.startFrom, 10) || null;
                if (linkPk && translationId) {
                    highlightTranslationButton(translationButton);
                    loadPlayer(linkPk, translationId, startFrom);
                } else {
                    console.error("Translation button clicked but no link PK or translation ID found.");
                }
            }
        });
    }

    if (nextEpisodeBtn) {
        nextEpisodeBtn.addEventListener('click', () => {
            if (currentLayout !== 'player_only') {
                const nextElement = findNextEpisodeElement(currentEpisodeElement);
                if (nextElement) {
                    handleEpisodeSelection(nextElement, true);
                }
            }
        });
    }

    if (prevEpisodeBtn) {
        prevEpisodeBtn.addEventListener('click', () => {
            if (currentLayout !== 'player_only') {
                const prevElement = findPrevEpisodeElement(currentEpisodeElement);
                if (prevElement) {
                    handleEpisodeSelection(prevElement, true);
                }
            }
        });
    }

    const detailTabs = document.querySelectorAll('#detail-tabs button[data-bs-toggle="tab"]');
    detailTabs.forEach(tabButton => {
        tabButton.addEventListener('shown.bs.tab', event => {
            if (LAST_DETAIL_TAB_KEY) {
                const activeTabTarget = event.target.getAttribute('data-bs-target');
                if (activeTabTarget) {
                    localStorage.setItem(LAST_DETAIL_TAB_KEY, activeTabTarget);
                    console.log(`Saved active detail tab: ${activeTabTarget}`);
                }
            }
        });
    });

    layoutRadios.forEach(radio => {
        radio.addEventListener('change', (event) => {
            console.log(`Layout radio changed: ID='${event.target.id}', Value='${event.target.value}', Checked=${event.target.checked}`);
            if (event.target.checked) {
                applyLayoutPreference(event.target.value, false);
            }
        });
    });

    // --- Initializations ---
    console.log("Media detail handler initializing...");
    episodesLinksData = parseJsonData(episodesLinksDataElement, 'Episodes links');
    mainLinksData = parseJsonData(mainLinksDataElement, 'Main links');
    jsTranslations = parseJsonData(jsTranslationsElement, 'JS Translations');
    // Get Track History URL and Auth Status
    trackHistoryUrl = trackHistoryUrlElement?.dataset.url;
    isUserAuthenticated = userAuthStatusElement?.dataset.isAuthenticated === 'true';
    csrfToken = csrfTokenInput?.value; // Get CSRF token once

    checkPlayerOnlyAvailability();
    initializeLayout();
    restoreLastDetailTab();
    setTimeout(() => {
        restoreLastWatchedState();
    }, 50);
    updateNavButtons();
    console.log("Media detail handler initialization complete. Auth Status:", isUserAuthenticated, "Track URL:", trackHistoryUrl, "CSRF Found:", !!csrfToken);

}); // End DOMContentLoaded