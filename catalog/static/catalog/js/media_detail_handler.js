// catalog/static/catalog/js/media_detail_handler.js
document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const playerPlaceholder = document.getElementById('player-placeholder');
    const episodesContainer = document.getElementById('seasons-tab-content');
    const nextEpisodeBtn = document.getElementById('next-episode-btn');
    const prevEpisodeBtn = document.getElementById('prev-episode-btn');
    const playerUrlTemplateEl = document.getElementById('player-url-template');
    const translationSelectorPlaceholder = document.getElementById('translation-selector-placeholder');
    const episodesLinksDataElement = document.getElementById('episodes-links-data');
    const mainLinksDataElement = document.getElementById('main-links-data');
    const mediaPk = episodesContainer?.dataset.mediaPk;
    const watchAreaContainer = document.getElementById('watch-area-container');
    const episodeListColumn = document.getElementById('episodes-container-column');
    const layoutRadios = document.querySelectorAll('input[name="playerLayout"]');
    const playerOnlyRadio = document.getElementById('layoutPlayerOnly');
    const playerOnlyLabel = document.querySelector('label[for="layoutPlayerOnly"]');

    // --- State Variables ---
    let currentEpisodeElement = null;
    let currentSelectedTranslationId = null;
    let episodesLinksData = {};
    let mainLinksData = {};
    let currentLayout = 'episodes-below'; // Initialize with default

    // --- Constants ---
    const LAST_EPISODE_KEY = mediaPk ? `last_watched_episode_${mediaPk}` : null;
    const LAST_TRANSLATION_KEY = mediaPk ? `last_selected_translation_${mediaPk}` : null;
    const LAST_DETAIL_TAB_KEY = mediaPk ? `last_detail_tab_${mediaPk}` : null;
    const PLAYER_LAYOUT_KEY = `player_layout_preference`;
    const PLAYER_URL_TEMPLATE = playerUrlTemplateEl?.dataset.url;
    const LAYOUTS = ['episodes_below', 'episodes_right', 'player_only']; // Valid layout values

    // --- Utility Functions ---
    function parseJsonData(element, description) {
        // ... (no changes needed)
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
        // ... (no changes needed)
        if (!PLAYER_URL_TEMPLATE || !linkPk) return null;
        return PLAYER_URL_TEMPLATE.replace(/catalog\/play\/\d+\//, `catalog/play/${linkPk}/`);
    }

    function getStartFromValue(linkData) {
        // ... (no changes needed)
        return linkData?.start_from ?? null;
    }

    // --- Core Logic Functions ---

    function loadPlayer(linkPk, translationIdToSave, startFrom = null) {
        // ... (no changes needed, logging already present)
        const playerUrl = generatePlayerUrl(linkPk);
        console.log(`Attempting to load player for link PK: ${linkPk}, Translation ID: ${translationIdToSave}, URL: ${playerUrl}, StartFrom: ${startFrom}`);

        if (playerUrl && playerPlaceholder) {
            playerPlaceholder.innerHTML = `
                <div class="player-container">
                    <iframe src="${playerUrl}"
                            allowfullscreen="allowfullscreen"
                            webkitallowfullscreen="webkitallowfullscreen"
                            mozallowfullscreen="mozallowfullscreen"
                            loading="eager">
                    </iframe>
                </div>`;

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

    function displayTranslationOptions(episodePk, preferredTranslationId = null) {
        // ... (no changes needed, logging already present)
        if (!translationSelectorPlaceholder) return null;

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


        let buttonsHtml = '';
        let translationLinkToAutoLoad = null;

        if (links.length > 0) {
            buttonsHtml = `<span class="me-2 small">{% trans "Translation" %}:</span>`;
            let preferredLink = null;

            if (preferredTranslationId) {
                preferredLink = links.find(link => link.translation_id == preferredTranslationId);
                 console.log(`Preferred translation ID ${preferredTranslationId} found in links: ${!!preferredLink}`);
            }

            translationLinkToAutoLoad = preferredLink || links[0];
             console.log(`Auto-loading translation: ${translationLinkToAutoLoad?.translation_title} (PK: ${translationLinkToAutoLoad?.link_pk})`);

            links.forEach(link => {
                const quality = link.quality ? ` (${link.quality})` : '';
                const isSelected = translationLinkToAutoLoad && link.link_pk === translationLinkToAutoLoad.link_pk;
                const btnClass = isSelected ? 'btn-primary active' : 'btn-outline-primary';
                buttonsHtml += `
                    <button class="btn btn-sm ${btnClass} me-1 mb-1 translation-btn"
                            data-link-pk="${link.link_pk}"
                            data-translation-id="${link.translation_id}"
                            data-start-from="${link.start_from ?? ''}">
                        ${link.translation_title}${quality}
                    </button>`;
            });
            translationSelectorPlaceholder.innerHTML = buttonsHtml;
             return translationLinkToAutoLoad;

        } else {
            translationSelectorPlaceholder.innerHTML = `<span class="text-warning small">{% trans "No translations available." %}</span>`;
             if (playerPlaceholder) {
                 playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "No content available." %}</div>';
             }
            return null;
        }
    }


    function highlightEpisode(episodeElement) {
       // ... (no changes needed)
        episodesContainer?.querySelectorAll('.episode-selector.border-primary').forEach(el => {
            el.classList.remove('border', 'border-primary', 'border-3');
        });
        if (episodeElement) {
            episodeElement.classList.add('border', 'border-primary', 'border-3');
            currentEpisodeElement = episodeElement;
            if (currentLayout === 'episodes_right') {
                episodeElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        } else {
            currentEpisodeElement = null;
        }
        updateNavButtons();
    }

    function highlightTranslationButton(buttonElement) {
        // ... (no changes needed)
         translationSelectorPlaceholder?.querySelectorAll('.translation-btn.active').forEach(btn => {
            btn.classList.remove('active', 'btn-primary');
            btn.classList.add('btn-outline-primary');
        });
        if (buttonElement) {
            buttonElement.classList.remove('btn-outline-primary');
            buttonElement.classList.add('active', 'btn-primary');
        }
    }

    function findEpisodeElementByPk(episodePk) {
        // ... (no changes needed)
        if (!episodesContainer || !episodePk) return null;
        return episodesContainer.querySelector(`.episode-selector[data-episode-pk='${episodePk}']`);
    }

    // --- Navigation and State Restoration ---

    function findNextEpisodeElement(currentElement) {
        // ... (no changes needed)
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
            if (nextTabButton) { try { new bootstrap.Tab(nextTabButton).show(); } catch(e){console.error("Bootstrap tab error:", e)} }
            return nextTabPane.querySelector('.episode-selector');
        }
        return null;
    }

    function findPrevEpisodeElement(currentElement) {
       // ... (no changes needed)
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
            if (prevTabButton) { try { new bootstrap.Tab(prevTabButton).show(); } catch(e){console.error("Bootstrap tab error:", e)} }
            const episodes = prevTabPane.querySelectorAll('.episode-selector');
            return episodes.length > 0 ? episodes[episodes.length - 1] : null;
        }
        return null;
    }


    function updateNavButtons() {
       // ... (no changes needed)
        const nextElement = findNextEpisodeElement(currentEpisodeElement);
        const prevElement = findPrevEpisodeElement(currentEpisodeElement);
        if (nextEpisodeBtn) nextEpisodeBtn.disabled = !nextElement || currentLayout === 'player_only';
        if (prevEpisodeBtn) prevEpisodeBtn.disabled = !prevElement || currentLayout === 'player_only';
    }

    function handleEpisodeSelection(episodeElement, manuallyClicked = false) {
        // ... (no changes needed, logging already present)
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
            const translationButton = translationSelectorPlaceholder?.querySelector(`.translation-btn[data-link-pk='${translationLinkToLoad.link_pk}']`);
            highlightTranslationButton(translationButton);
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
            try { new bootstrap.Tab(watchTabButton).show(); } catch(e) {console.error("Bootstrap tab error:", e)}
        }
    }

    function restoreLastWatchedState() {
        // ... (no changes needed, logging already present)
        // Only restore episode if NOT in player_only mode initially
        if (currentLayout === 'player_only') {
            console.log("Restore Watched State: In player_only layout.");
            const preferredTranslationId = LAST_TRANSLATION_KEY ? localStorage.getItem(LAST_TRANSLATION_KEY) : null;
            const mainTranslationLink = displayTranslationOptions(null, preferredTranslationId);
            if (mainTranslationLink) {
                const startFrom = getStartFromValue(mainTranslationLink);
                loadPlayer(mainTranslationLink.link_pk, mainTranslationLink.translation_id.toString(), startFrom);
                 const mainTranslationButton = translationSelectorPlaceholder?.querySelector(`.translation-btn[data-link-pk='${mainTranslationLink.link_pk}']`);
                 highlightTranslationButton(mainTranslationButton);
            } else {
                 if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select a translation to start watching" %}</div>';
            }
            return;
        }

        // Restore episode state for other layouts
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
                         // Use 'shown.bs.tab' event to ensure tab content is visible before selecting
                         targetSeasonButton.addEventListener('shown.bs.tab', () => {
                             console.log(`Restore Watched State: Tab shown for ${targetTabPaneId}, selecting episode.`);
                             handleEpisodeSelection(lastEpisodeElement, false);
                         }, { once: true }); // Ensure listener runs only once
                         new bootstrap.Tab(targetSeasonButton).show();
                    } catch(e){
                        console.error("Bootstrap tab error during restore:", e);
                        handleEpisodeSelection(lastEpisodeElement, false); // Fallback
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


    function restoreLastDetailTab() {
        // ... (no changes needed)
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
             if(defaultTabButton && !defaultTabButton.classList.contains('active')) {
                 try { new bootstrap.Tab(defaultTabButton).show(); } catch(e){}
             }
        }
    }

    /**
     * Applies the selected player layout by adding/removing classes and adjusting visibility.
     * @param {string} layout - The layout identifier ('episodes_below', 'episodes_right', 'player_only').
     * @param {boolean} [triggeredByInitialization=false] - Indicates if the call comes from initial page load.
     */
    function applyLayoutPreference(layout, triggeredByInitialization = false) {
        // Add logging at the beginning
        console.log(`ApplyLayoutPreference called with layout: '${layout}', Initializing: ${triggeredByInitialization}`);

        if (!watchAreaContainer || !episodeListColumn) {
             console.error("Layout containers not found!");
             return;
        }

        // --- Validate Layout ---
        const chosenLayout = LAYOUTS.includes(layout) ? layout : 'episodes_below';
        console.log(`Chosen layout: '${chosenLayout}'`);

        // --- Prevent redundant application ---
        // Check if the new layout is the same as the current one already applied to the DOM
        if (watchAreaContainer.classList.contains(`layout-${chosenLayout}`) && !triggeredByInitialization) {
             console.log(`Layout '${chosenLayout}' is already applied. Skipping redundant application.`);
             return;
        }

        const previousLayout = currentLayout; // Store previous layout before updating
        currentLayout = chosenLayout; // Update global state

        // --- Update Container Class ---
        watchAreaContainer.classList.remove(...LAYOUTS.map(l => `layout-${l}`)); // More specific removal
        watchAreaContainer.classList.add(`layout-${chosenLayout}`);
        console.log(`Applied CSS class: layout-${chosenLayout}`);

        // --- Save Preference ---
        localStorage.setItem(PLAYER_LAYOUT_KEY, chosenLayout);
        console.log(`Saved preference to localStorage: ${chosenLayout}`);

        // --- Update Radio Buttons ---
        LAYOUTS.forEach(lKey => {
            const radio = document.getElementById(`layout${lKey.split('_').map(s=>s.charAt(0).toUpperCase()+s.slice(1)).join('')}`);
            if(radio) {
                radio.checked = (lKey === chosenLayout);
            }
        });

        // --- Update based on new layout ---
        updateNavButtons();

        // --- Handle transitions ---
        // Only run transition logic if the layout actually changed
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
                    const mainTranslationButton = translationSelectorPlaceholder?.querySelector(`.translation-btn[data-link-pk='${mainTranslationLink.link_pk}']`);
                    highlightTranslationButton(mainTranslationButton);
                } else {
                    if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select a translation to start watching" %}</div>';
                    highlightTranslationButton(null);
                }
            } else if (previousLayout === 'player_only') {
                // Transitioning FROM player_only
                console.log("Transitioning from player_only mode...");
                 const lastEpisodePk = LAST_EPISODE_KEY ? localStorage.getItem(LAST_EPISODE_KEY) : null;
                 const lastEpisodeElement = lastEpisodePk ? findEpisodeElementByPk(lastEpisodePk) : null;
                 if (lastEpisodeElement) {
                     handleEpisodeSelection(lastEpisodeElement, false);
                 } else {
                     // No last episode, clear player/translations
                      if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select an episode to start watching" %}</div>';
                     if (translationSelectorPlaceholder) translationSelectorPlaceholder.innerHTML = '';
                     highlightEpisode(null);
                     highlightTranslationButton(null);
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
        applyLayoutPreference(layoutToApply, true); // Pass true for initialization flag
    }

    function checkPlayerOnlyAvailability() {
        // ... (no changes needed)
        const hasMainLinks = Object.keys(mainLinksData).length > 0;
        if (!hasMainLinks && playerOnlyRadio && playerOnlyLabel) {
            console.log("Disabling player_only layout option: No main links found.");
            playerOnlyRadio.disabled = true;
            playerOnlyLabel.classList.add('disabled', 'opacity-50');
            playerOnlyLabel.title = '{% trans "Player only option unavailable (no main item link found)" %}';
            // DO NOT switch layout here, initializeLayout will handle the fallback later
            // if (localStorage.getItem(PLAYER_LAYOUT_KEY) === 'player_only') {
            //     applyLayoutPreference('episodes_below'); // Incorrect place
            // }
        } else if (playerOnlyRadio) {
             playerOnlyRadio.disabled = false;
             playerOnlyLabel?.classList.remove('disabled', 'opacity-50');
             playerOnlyLabel.title = '{% trans "Player only (hide episodes)" %}';
        }
    }

    // --- Event Listeners ---

    if (episodesContainer) {
        episodesContainer.addEventListener('click', (event) => {
           // ... (no changes needed)
            const episodeCard = event.target.closest('.episode-selector');
            if (episodeCard && currentLayout !== 'player_only') {
                event.preventDefault();
                handleEpisodeSelection(episodeCard, true);
            }
        });
    }

    if (translationSelectorPlaceholder) {
        translationSelectorPlaceholder.addEventListener('click', (event) => {
            // ... (no changes needed)
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
           // ... (no changes needed)
            if (currentLayout !== 'player_only') {
                const nextElement = findNextEpisodeElement(currentEpisodeElement);
                if (nextElement) { handleEpisodeSelection(nextElement, true); }
            }
        });
    }
    if (prevEpisodeBtn) {
        prevEpisodeBtn.addEventListener('click', () => {
            // ... (no changes needed)
             if (currentLayout !== 'player_only') {
                 const prevElement = findPrevEpisodeElement(currentEpisodeElement);
                 if (prevElement) { handleEpisodeSelection(prevElement, true); }
             }
        });
    }

    const detailTabs = document.querySelectorAll('#detail-tabs button[data-bs-toggle="tab"]');
    detailTabs.forEach(tabButton => {
        // ... (no changes needed)
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

    // Player Layout Radio Button Changes
    layoutRadios.forEach(radio => {
        radio.addEventListener('change', (event) => {
             // Add logging here
             console.log(`Layout radio changed: ID='${event.target.id}', Value='${event.target.value}', Checked=${event.target.checked}`);
            if (event.target.checked) {
                // Pass the NEWLY selected value to applyLayoutPreference
                applyLayoutPreference(event.target.value, false); // False = not initialization
            }
        });
    });


    // --- Initializations ---
    console.log("Media detail handler initializing...");
    episodesLinksData = parseJsonData(episodesLinksDataElement, 'Episodes links');
    mainLinksData = parseJsonData(mainLinksDataElement, 'Main links');
    checkPlayerOnlyAvailability(); // Run check *before* initializing layout
    initializeLayout();          // Initialize layout based on storage/availability
    restoreLastDetailTab();      // Restore Details/Watch tab
    restoreLastWatchedState();   // Restore episode/translation *after* layout is set
    updateNavButtons();          // Ensure nav buttons reflect initial state

    console.log("Media detail handler initialization complete.");

}); // End DOMContentLoaded