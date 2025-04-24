// catalog/static/catalog/js/media_detail_handler.js
document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const playerPlaceholder = document.getElementById('player-placeholder');
    const episodesContainer = document.getElementById('seasons-tab-content');
    const nextEpisodeBtn = document.getElementById('next-episode-btn');
    const prevEpisodeBtn = document.getElementById('prev-episode-btn');
    const playerUrlTemplateEl = document.getElementById('player-url-template');
    // Translation elements
    const translationSelectorPlaceholder = document.getElementById('translation-selector-placeholder'); // Main container
    const translationLabel = translationSelectorPlaceholder?.querySelector('.translation-label'); // Static label
    const translationButtonsContainer = document.getElementById('translation-buttons-container'); // Buttons go here
    const noTranslationsMessage = document.getElementById('no-translations-message'); // Message span
    // ---
    const episodesLinksDataElement = document.getElementById('episodes-links-data');
    const mainLinksDataElement = document.getElementById('main-links-data');
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
    let currentLayout = 'episodes_below';

    // --- Constants ---
    const LAST_EPISODE_KEY = mediaPk ? `last_watched_episode_${mediaPk}` : null;
    const LAST_TRANSLATION_KEY = mediaPk ? `last_selected_translation_${mediaPk}` : null;
    const LAST_DETAIL_TAB_KEY = mediaPk ? `last_detail_tab_${mediaPk}` : null;
    const PLAYER_LAYOUT_KEY = `player_layout_preference`;
    const PLAYER_URL_TEMPLATE = playerUrlTemplateEl?.dataset.url;
    const LAYOUTS = ['episodes_below', 'episodes_right', 'player_only'];
    const SCROLL_CLASS = 'episodes-sidebar-scroll';

    // --- Utility Functions ---
    function parseJsonData(element, description) { /* ... no changes ... */
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

    function generatePlayerUrl(linkPk) { /* ... no changes ... */
        if (!PLAYER_URL_TEMPLATE || !linkPk) return null;
        return PLAYER_URL_TEMPLATE.replace(/catalog\/play\/\d+\//, `catalog/play/${linkPk}/`);
    }

    function getStartFromValue(linkData) { /* ... no changes ... */
        return linkData?.start_from ?? null;
    }

    // --- Core Logic Functions ---
    function loadPlayer(linkPk, translationIdToSave, startFrom = null) { /* ... no changes ... */
        const playerUrl = generatePlayerUrl(linkPk);
        console.log(`Attempting to load player for link PK: ${linkPk}, Translation ID: ${translationIdToSave}, URL: ${playerUrl}, StartFrom: ${startFrom}`);
        if (playerUrl && playerPlaceholder) {
            playerPlaceholder.innerHTML = `<div class="player-container"><iframe src="${playerUrl}" allowfullscreen="allowfullscreen" webkitallowfullscreen="webkitallowfullscreen" mozallowfullscreen="mozallowfullscreen" loading="eager"></iframe></div>`;
            if (LAST_TRANSLATION_KEY && translationIdToSave) {
                localStorage.setItem(LAST_TRANSLATION_KEY, translationIdToSave);
                currentSelectedTranslationId = translationIdToSave.toString();
                console.log(`Saved last translation ID: ${currentSelectedTranslationId}`);
            }
            if (currentEpisodeElement && LAST_EPISODE_KEY) {
                const episodePk = currentEpisodeElement.dataset.episodePk;
                localStorage.setItem(LAST_EPISODE_KEY, episodePk);
                console.log(`Saved last episode PK: ${episodePk}`);
            } else if (!currentEpisodeElement && LAST_EPISODE_KEY && currentLayout === 'player_only') {
                console.log("In player_only mode, keeping last episode PK if previously set.");
            }
        } else {
            console.error('Could not generate player URL or player placeholder not found.');
            playerPlaceholder.innerHTML = '<p class="text-danger text-center p-5">{% trans "Error loading player." %}</p>';
        }
    }

    /**
     * Displays translation buttons based on available links for the current context.
     * Updates the content of #translation-buttons-container and visibility of related elements.
     * @param {string|null} episodePk - PK of the episode, or null if in 'player_only' layout.
     * @param {string|null} preferredTranslationId - Kodik ID of the translation to pre-select.
     * @returns {object|null} The link object of the translation to auto-load, or null.
     */
    function displayTranslationOptions(episodePk, preferredTranslationId = null) {
        // Ensure the target containers exist
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

        // Clear previous buttons and hide messages/label initially
        translationButtonsContainer.innerHTML = '';
        translationLabel.style.display = 'none';
        noTranslationsMessage.style.display = 'none';

        let translationLinkToAutoLoad = null;

        if (links.length > 0) {
            translationLabel.style.display = ''; // Show the static label

            let preferredLink = null;
            if (preferredTranslationId) {
                preferredLink = links.find(link => link.translation_id == preferredTranslationId);
                console.log(`Preferred translation ID ${preferredTranslationId} found in links: ${!!preferredLink}`);
            }
            translationLinkToAutoLoad = preferredLink || links[0];
            console.log(`Auto-loading translation: ${translationLinkToAutoLoad?.translation_title} (PK: ${translationLinkToAutoLoad?.link_pk})`);

            // Generate buttons HTML and append to the container
            let buttonsHtml = '';
            links.forEach(link => {
                const quality = link.quality ? ` (${link.quality})` : '';
                const isSelected = translationLinkToAutoLoad && link.link_pk === translationLinkToAutoLoad.link_pk;
                const btnClass = isSelected ? 'btn-primary active' : 'btn-outline-primary';
                buttonsHtml += `<button class="btn btn-sm ${btnClass} me-1 mb-1 translation-btn" data-link-pk="${link.link_pk}" data-translation-id="${link.translation_id}" data-start-from="${link.start_from ?? ''}">${link.translation_title}${quality}</button>`;
            });
            translationButtonsContainer.innerHTML = buttonsHtml; // Set buttons HTML
            return translationLinkToAutoLoad;

        } else {
            noTranslationsMessage.style.display = ''; // Show the 'no translations' message
            if (playerPlaceholder) {
                playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "No content available." %}</div>';
            }
            return null;
        }
    }

    function highlightEpisode(episodeElement) { /* ... no changes ... */
        document.querySelectorAll('#seasons-tab-content .episode-selector.border-primary').forEach(el => {
            el.classList.remove('border', 'border-primary', 'border-3');
        });
        if (episodeElement) {
            episodeElement.classList.add('border', 'border-primary', 'border-3');
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
        // Target buttons within the specific container now
        translationButtonsContainer?.querySelectorAll('.translation-btn.active').forEach(btn => {
            btn.classList.remove('active', 'btn-primary');
            btn.classList.add('btn-outline-primary');
        });
        if (buttonElement) {
            buttonElement.classList.remove('btn-outline-primary');
            buttonElement.classList.add('active', 'btn-primary');
        }
    }

    function findEpisodeElementByPk(episodePk) { /* ... no changes ... */
        if (!episodesContainer || !episodePk) return null;
        return episodesContainer.querySelector(`.episode-selector[data-episode-pk='${episodePk}']`);
    }

    // --- Navigation and State Restoration ---
    function findNextEpisodeElement(currentElement) { /* ... no changes ... */
        if (!currentElement) return null;
        const currentCol = currentElement.closest('.col');
        if (!currentCol) return null;
        let nextCol = currentCol.nextElementSibling;
        while (nextCol && !nextCol.querySelector('.episode-selector')) {
            nextCol = nextCol.nextElementSibling;
        }
        if (nextCol?.querySelector('.episode-selector')) {
            return nextCol.querySelector('.episode-selector');
        }
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
            return nextTabPane.querySelector('.episode-selector');
        }
        return null;
    }

    function findPrevEpisodeElement(currentElement) { /* ... no changes ... */
        if (!currentElement) return null;
        const currentCol = currentElement.closest('.col');
        if (!currentCol) return null;
        let prevCol = currentCol.previousElementSibling;
        while (prevCol && !prevCol.querySelector('.episode-selector')) {
            prevCol = prevCol.previousElementSibling;
        }
        if (prevCol?.querySelector('.episode-selector')) {
            return prevCol.querySelector('.episode-selector');
        }
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
            return episodes.length > 0 ? episodes[episodes.length - 1] : null;
        }
        return null;
    }

    function updateNavButtons() { /* ... no changes ... */
        const nextElement = findNextEpisodeElement(currentEpisodeElement);
        const prevElement = findPrevEpisodeElement(currentEpisodeElement);
        const navContainer = episodeListColumn?.querySelector('.d-flex.justify-content-between.align-items-center'); // Find container of nav buttons/title
        if (navContainer) {
            navContainer.style.display = (currentLayout === 'player_only') ? 'none' : ''; // Hide container in player_only
        }
        if (nextEpisodeBtn) nextEpisodeBtn.disabled = !nextElement || currentLayout === 'player_only';
        if (prevEpisodeBtn) prevEpisodeBtn.disabled = !prevElement || currentLayout === 'player_only';
    }

    function handleEpisodeSelection(episodeElement, manuallyClicked = false) { /* ... no changes ... */
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
            highlightTranslationButton(translationButton); // Target container
        } else {
            console.log(`No translation link to load for episode PK ${episodePk}`);
            if (playerPlaceholder) {
                playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "No translations found for this episode." %}</div>';
            }
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

    function restoreLastWatchedState() { /* ... no changes ... */
        if (currentLayout === 'player_only') {
            console.log("Restore Watched State: In player_only layout.");
            const preferredTranslationId = LAST_TRANSLATION_KEY ? localStorage.getItem(LAST_TRANSLATION_KEY) : null;
            const mainTranslationLink = displayTranslationOptions(null, preferredTranslationId);
            if (mainTranslationLink) {
                const startFrom = getStartFromValue(mainTranslationLink);
                loadPlayer(mainTranslationLink.link_pk, mainTranslationLink.translation_id.toString(), startFrom);
                const mainTranslationButton = translationButtonsContainer?.querySelector(`.translation-btn[data-link-pk='${mainTranslationLink.link_pk}']`);
                highlightTranslationButton(mainTranslationButton);
            } // Target container
            else {
                if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select a translation to start watching" %}</div>';
            }
            return;
        }
        console.log("Restore Watched State: Checking for last episode...");
        if (!LAST_EPISODE_KEY) {
            console.log("Restore Watched State: No episode key defined.");
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
                    try {
                        console.log(`Restore Watched State: Activating season tab for episode ${lastEpisodePk}`);
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
            }
        } else {
            console.log("Restore Watched State: No last watched episode found in localStorage.");
        }
    }

    function restoreLastDetailTab() { /* ... no changes ... */
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

    function applyLayoutPreference(layout, triggeredByInitialization = false) { /* ... no changes to main logic, only translation handling changed ... */
        console.log(`ApplyLayoutPreference called with layout: '${layout}', Initializing: ${triggeredByInitialization}`);
        if (!playerContainerColumn || !episodeListColumn) {
            console.error("Layout columns not found in DOM!");
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
        let playerClasses = ['col-12'];
        let episodeClasses = ['col-12'];
        let episodeHidden = false;
        let episodeMarginTop = true;
        let addScrollClass = false;
        switch (chosenLayout) {
            case 'episodes_right':
                playerClasses = ['col-lg-8', 'col-md-12'];
                episodeClasses = ['col-lg-4', 'col-md-12'];
                episodeMarginTop = false;
                addScrollClass = true;
                break;
            case 'player_only':
                episodeHidden = true;
                episodeMarginTop = false;
                break;
            case 'episodes_below':
            default:
                episodeMarginTop = true;
                break;
        }
        console.log(`Applying classes - Player: ${playerClasses.join(' ')}, Episodes: ${episodeClasses.join(' ')}, Hidden: ${episodeHidden}, MarginTop: ${episodeMarginTop}, Scroll: ${addScrollClass}`);
        playerContainerColumn.className = 'col-12';
        playerContainerColumn.classList.add(...playerClasses);
        episodeListColumn.className = 'col-12';
        episodeListColumn.classList.add(...episodeClasses);
        if (episodeHidden) {
            episodeListColumn.classList.add('d-none');
        } else {
            episodeListColumn.classList.remove('d-none');
        }
        if (episodeMarginTop) {
            episodeListColumn.classList.add('mt-lg-0', 'mt-3');
            if (chosenLayout === 'episodes_right') {
                episodeListColumn.classList.remove('mt-3');
                playerContainerColumn.classList.add('mb-3', 'mb-lg-0');
            } else {
                playerContainerColumn.classList.remove('mb-3', 'mb-lg-0');
            }
        } else {
            episodeListColumn.classList.remove('mt-lg-0', 'mt-3');
            playerContainerColumn.classList.remove('mb-3', 'mb-lg-0');
        }
        if (addScrollClass) {
            episodeListColumn.classList.add(SCROLL_CLASS);
        } else {
            episodeListColumn.classList.remove(SCROLL_CLASS);
        }
        localStorage.setItem(PLAYER_LAYOUT_KEY, chosenLayout);
        console.log(`Saved preference to localStorage: ${chosenLayout}`);
        layoutRadios.forEach(radio => {
            radio.checked = (radio.value === chosenLayout);
        });
        updateNavButtons(); // Update before potential player load
        if (previousLayout !== chosenLayout) {
            console.log(`Layout changed from '${previousLayout}' to '${chosenLayout}'`);
            if (chosenLayout === 'player_only') {
                console.log("Transitioning to player_only mode...");
                highlightEpisode(null);
                const preferredTranslationId = currentSelectedTranslationId || (LAST_TRANSLATION_KEY ? localStorage.getItem(LAST_TRANSLATION_KEY) : null);
                const mainTranslationLink = displayTranslationOptions(null, preferredTranslationId); // This will update buttons in the container
                if (mainTranslationLink) {
                    const startFrom = getStartFromValue(mainTranslationLink);
                    loadPlayer(mainTranslationLink.link_pk, mainTranslationLink.translation_id.toString(), startFrom);
                    const mainTranslationButton = translationButtonsContainer?.querySelector(`.translation-btn[data-link-pk='${mainTranslationLink.link_pk}']`);
                    highlightTranslationButton(mainTranslationButton);
                } // Target container
                else {
                    if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select a translation to start watching" %}</div>';
                    highlightTranslationButton(null);
                }
            } else if (previousLayout === 'player_only') {
                console.log("Transitioning from player_only mode...");
                const lastEpisodePk = LAST_EPISODE_KEY ? localStorage.getItem(LAST_EPISODE_KEY) : null;
                const lastEpisodeElement = lastEpisodePk ? findEpisodeElementByPk(lastEpisodePk) : null;
                if (lastEpisodeElement) {
                    handleEpisodeSelection(lastEpisodeElement, false);
                } // This calls displayTranslationOptions for the episode
                else {
                    if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select an episode to start watching" %}</div>';
                    if (translationButtonsContainer) translationButtonsContainer.innerHTML = '';
                    if (translationLabel) translationLabel.style.display = 'none';
                    if (noTranslationsMessage) noTranslationsMessage.style.display = 'none';
                    highlightEpisode(null);
                    highlightTranslationButton(null);
                }
            } else {
                if (currentEpisodeElement) {
                    highlightEpisode(currentEpisodeElement);
                } else { /* Maybe load first episode or clear translations? Let's clear */
                    if (translationButtonsContainer) translationButtonsContainer.innerHTML = '';
                    if (translationLabel) translationLabel.style.display = 'none';
                    if (noTranslationsMessage) noTranslationsMessage.style.display = 'none';
                }
            }
        } else {
            console.log(`Layout '${chosenLayout}' was already set, no transition logic needed.`);
        }
    }

    function initializeLayout() { /* ... no changes ... */
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

    function checkPlayerOnlyAvailability() { /* ... no changes ... */
        const hasMainLinks = Object.keys(mainLinksData).length > 0;
        if (!hasMainLinks && playerOnlyRadio && playerOnlyLabel) {
            console.log("Disabling player_only layout option: No main links found.");
            playerOnlyRadio.disabled = true;
            playerOnlyLabel.classList.add('disabled', 'opacity-50');
            playerOnlyLabel.title = '{% trans "Player only option unavailable (no main item link found)" %}';
        } else if (playerOnlyRadio) {
            playerOnlyRadio.disabled = false;
            playerOnlyLabel?.classList.remove('disabled', 'opacity-50');
            playerOnlyLabel.title = '{% trans "Player only (hide episodes)" %}';
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
    // UPDATED: Target the buttons container for delegation
    if (translationButtonsContainer) {
        translationButtonsContainer.addEventListener('click', (event) => {
            const translationButton = event.target.closest('.translation-btn');
            if (translationButton) {
                event.preventDefault();
                const linkPk = translationButton.dataset.linkPk;
                const translationId = translationButton.dataset.translationId;
                const startFrom = parseInt(translationButton.dataset.startFrom) || null;
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
    checkPlayerOnlyAvailability();
    initializeLayout();
    restoreLastDetailTab();
    setTimeout(() => {
        restoreLastWatchedState();
    }, 50);
    updateNavButtons(); // Update nav buttons visibility based on initial layout
    console.log("Media detail handler initialization complete.");

}); // End DOMContentLoaded