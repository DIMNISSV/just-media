// catalog/static/catalog/js/media_detail_handler.js
document.addEventListener('DOMContentLoaded', () => {
    const playerPlaceholder = document.getElementById('player-placeholder');
    const mediaDescription = document.getElementById('media-description'); // Still needed? No, it's in another tab
    const episodesContainer = document.getElementById('seasons-tab-content'); // Container for all season panes
    const nextEpisodeBtn = document.getElementById('next-episode-btn');
    const prevEpisodeBtn = document.getElementById('prev-episode-btn');
    const playerUrlTemplate = document.getElementById('player-url-template')?.dataset.url;
    const translationSelectorPlaceholder = document.getElementById('translation-selector-placeholder');
    const episodesLinksDataElement = document.getElementById('episodes-links-data');
    const mediaPk = episodesContainer?.dataset.mediaPk; // Check if container exists

    let episodesLinksData = {};
    try {
        if (episodesLinksDataElement) {
            episodesLinksData = JSON.parse(episodesLinksDataElement.textContent || '{}');
        }
    } catch (e) {
        console.error("Error parsing episodes links data:", e);
    }

    let currentEpisodeElement = null;
    let currentSelectedTranslationId = null;

    const lastEpisodeKey = mediaPk ? `last_watched_episode_${mediaPk}` : null;
    const lastTranslationKey = mediaPk ? `last_selected_translation_${mediaPk}` : null;
    const lastDetailTabKey = mediaPk ? `last_detail_tab_${mediaPk}` : null; // Key for saving active tab

    console.log("Media detail handler loaded. Media PK:", mediaPk);

    function generatePlayerUrl(linkPk) {
        if (!playerUrlTemplate || !linkPk) return null;
        return playerUrlTemplate.replace('/0/', `/${linkPk}/`);
    }

    function loadPlayer(linkPk, translationIdToSave) {
        const playerUrl = generatePlayerUrl(linkPk);
        console.log(`Attempting to load player for link PK: ${linkPk}, Translation ID: ${translationIdToSave}, URL: ${playerUrl}`);
        if (playerUrl && playerPlaceholder) {
            playerPlaceholder.innerHTML = `
                <div class="player-container" style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; background: #000;">
                    <iframe src="${playerUrl}"
                            style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
                            frameborder="0" scrolling="no" allowfullscreen="allowfullscreen"
                            webkitallowfullscreen="webkitallowfullscreen" mozallowfullscreen="mozallowfullscreen"
                            loading="lazy">
                    </iframe>
                </div>`;
            // Removed hiding description logic

            if (currentEpisodeElement && lastEpisodeKey) {
                const episodePk = currentEpisodeElement.dataset.episodePk;
                localStorage.setItem(lastEpisodeKey, episodePk);
                console.log(`Saved last episode PK: ${episodePk} to ${lastEpisodeKey}`);
            }
            if (translationIdToSave && lastTranslationKey) {
                localStorage.setItem(lastTranslationKey, translationIdToSave);
                console.log(`Saved last translation ID: ${translationIdToSave} to ${lastTranslationKey}`);
                currentSelectedTranslationId = translationIdToSave;
            }

        } else {
            console.error('Could not generate player URL or placeholder not found.');
            playerPlaceholder.innerHTML = '<p class="text-danger">Error loading player.</p>';
        }
    }

    function displayTranslationOptions(episodePk, preferredTranslationId = null) {
        if (!translationSelectorPlaceholder) return null;

        const links = episodesLinksData[episodePk] || [];
        console.log(`Translations found for episode PK ${episodePk}:`, links);

        let buttonsHtml = '';
        let translationToAutoLoad = null;

        if (links.length > 0) {
            buttonsHtml = '<span class="me-2 small">Choose translation:</span>'; // i18n
            let preferredLink = null;
            let firstLink = links[0];

            if (preferredTranslationId) {
                preferredLink = links.find(link => link.translation_id == preferredTranslationId);
            }
            translationToAutoLoad = preferredLink || firstLink;

            links.forEach(link => {
                const quality = link.quality ? `(${link.quality})` : '';
                const isSelected = translationToAutoLoad && link.link_pk === translationToAutoLoad.link_pk;
                const btnClass = isSelected ? 'btn-primary active' : 'btn-outline-primary';

                buttonsHtml += `
                    <button class="btn btn-sm ${btnClass} me-1 mb-1 translation-btn"
                            data-link-pk="${link.link_pk}"
                            data-translation-id="${link.translation_id}">
                        ${link.translation_title} ${quality}
                    </button>`;
            });
            translationSelectorPlaceholder.innerHTML = buttonsHtml;
            // Don't clear player if autoloading
            if (!translationToAutoLoad) {
                playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">Select a translation</div>'; // i18n
            }

        } else {
            translationSelectorPlaceholder.innerHTML = '<span class="text-warning small">No translations found for this episode.</span>'; // i18n
            playerPlaceholder.innerHTML = '';
        }
        return translationToAutoLoad;
    }

    function highlightEpisode(episodeElement) {
        // Use querySelectorAll within the main container to avoid issues with multiple grids if layout changes
        episodesContainer?.querySelectorAll('.episode-selector.border-primary').forEach(el => {
            el.classList.remove('border', 'border-primary', 'border-3');
        });

        if (episodeElement) {
            episodeElement.classList.add('border', 'border-primary', 'border-3');
            currentEpisodeElement = episodeElement;
            updateNavButtons();
        } else {
            currentEpisodeElement = null;
            updateNavButtons();
        }
    }

    function highlightTranslationButton(buttonElement) {
        translationSelectorPlaceholder?.querySelectorAll('.translation-btn.active').forEach(btn => {
            btn.classList.remove('active');
            btn.classList.replace('btn-primary', 'btn-outline-primary');
        });
        if (buttonElement) {
            buttonElement.classList.add('active');
            buttonElement.classList.replace('btn-outline-primary', 'btn-primary');
        }
    }

    function findEpisodeElementByPk(episodePk) {
        if (!episodesContainer || !episodePk) return null;
        return episodesContainer.querySelector(`.episode-selector[data-episode-pk='${episodePk}']`);
    }

    // findNextEpisodeElement and findPrevEpisodeElement remain the same as previous version

    function findNextEpisodeElement(currentElement) {
        if (!currentElement) return null;
        const currentContainer = currentElement.closest('.episodes-grid');
        if (!currentContainer) return null;

        const nextSibling = currentElement.closest('.col').nextElementSibling;
        if (nextSibling && nextSibling.querySelector('.episode-selector')) {
            return nextSibling.querySelector('.episode-selector');
        } else {
            const currentTabPane = currentElement.closest('.tab-pane');
            if (!currentTabPane) return null;
            const nextTabPane = currentTabPane.nextElementSibling;
            if (nextTabPane && nextTabPane.classList.contains('tab-pane')) {
                const nextTabButtonId = nextTabPane.getAttribute('aria-labelledby');
                const nextTabButton = document.getElementById(nextTabButtonId);
                if (nextTabButton) {
                    try {
                        new bootstrap.Tab(nextTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap Tab error:", e);
                    }
                }
                return nextTabPane.querySelector('.episode-selector');
            }
        }
        return null;
    }

    function findPrevEpisodeElement(currentElement) {
        if (!currentElement) return null;
        const currentContainer = currentElement.closest('.episodes-grid');
        if (!currentContainer) return null;

        const prevSibling = currentElement.closest('.col').previousElementSibling;
        if (prevSibling && prevSibling.querySelector('.episode-selector')) {
            return prevSibling.querySelector('.episode-selector');
        } else {
            const currentTabPane = currentElement.closest('.tab-pane');
            if (!currentTabPane) return null;
            const prevTabPane = currentTabPane.previousElementSibling;
            if (prevTabPane && prevTabPane.classList.contains('tab-pane')) {
                const prevTabButtonId = prevTabPane.getAttribute('aria-labelledby');
                const prevTabButton = document.getElementById(prevTabButtonId);
                if (prevTabButton) {
                    try {
                        new bootstrap.Tab(prevTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap Tab error:", e);
                    }
                }
                const episodesInPrev = prevTabPane.querySelectorAll('.episode-selector');
                return episodesInPrev.length > 0 ? episodesInPrev[episodesInPrev.length - 1] : null;
            }
        }
        return null;
    }


    function updateNavButtons() {
        const nextElement = findNextEpisodeElement(currentEpisodeElement);
        const prevElement = findPrevEpisodeElement(currentEpisodeElement);
        if (nextEpisodeBtn) nextEpisodeBtn.disabled = !nextElement;
        if (prevEpisodeBtn) prevEpisodeBtn.disabled = !prevElement;
    }

    function handleEpisodeSelection(episodeElement, manuallyClicked = false) {
        if (!episodeElement) return;

        const episodePk = episodeElement.dataset.episodePk;
        highlightEpisode(episodeElement);

        const preferredTranslationId = lastTranslationKey ? localStorage.getItem(lastTranslationKey) : null;
        const translationLinkToLoad = displayTranslationOptions(episodePk, preferredTranslationId);

        if (translationLinkToLoad) {
            console.log(`Autoloading player for episode ${episodePk} with translation ID ${translationLinkToLoad.translation_id}`);
            loadPlayer(translationLinkToLoad.link_pk, translationLinkToLoad.translation_id.toString());
            const translationButton = translationSelectorPlaceholder?.querySelector(`.translation-btn[data-link-pk='${translationLinkToLoad.link_pk}']`);
            highlightTranslationButton(translationButton);
        } else {
            playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">Select a translation</div>'; // i18n
            currentSelectedTranslationId = null;
            translationSelectorPlaceholder.innerHTML = ''; // Clear buttons if no link found on auto
        }
        // Ensure the "Watch" tab is active when an episode is selected
        const watchTabButton = document.getElementById('watch-tab');
        if (watchTabButton && !watchTabButton.classList.contains('active')) {
            try {
                new bootstrap.Tab(watchTabButton).show();
            } catch (e) {
                console.error("Bootstrap Tab error:", e);
            }
        }
    }

    function restoreLastWatchedState() {
        if (!lastEpisodeKey) return;

        const lastEpisodePk = localStorage.getItem(lastEpisodeKey);
        if (lastEpisodePk) {
            const lastEpisodeElement = findEpisodeElementByPk(lastEpisodePk);
            if (lastEpisodeElement) {
                console.log(`Restoring last watched episode: PK ${lastEpisodePk}`);
                const targetTabPaneId = lastEpisodeElement.closest('.tab-pane')?.id;
                const targetSeasonButton = targetTabPaneId ? document.querySelector(`button[data-bs-target='#${targetTabPaneId}']`) : null;
                if (targetSeasonButton) {
                    try {
                        new bootstrap.Tab(targetSeasonButton).show();
                    } catch (e) {
                        console.error("Bootstrap Tab error:", e);
                    }
                }
                // Use a small delay to ensure tab pane is visible before clicking
                setTimeout(() => {
                    handleEpisodeSelection(lastEpisodeElement, false);
                }, 100); // 100ms delay

            } else {
                console.log(`Could not find last watched episode element (PK ${lastEpisodePk}) in DOM.`);
            }
        } else {
            console.log("No last watched episode found in localStorage.");
        }
    }

    function restoreLastDetailTab() {
        if (!lastDetailTabKey) return;
        const lastTabId = localStorage.getItem(lastDetailTabKey);
        if (lastTabId) {
            const tabButton = document.querySelector(`#detail-tabs button[data-bs-target="${lastTabId}"]`);
            if (tabButton) {
                try {
                    new bootstrap.Tab(tabButton).show();
                } catch (e) {
                    console.error("Bootstrap Tab error:", e);
                }
                console.log(`Restored last active detail tab: ${lastTabId}`);
            }
        }
    }


    // --- Event Listeners ---
    if (episodesContainer) {
        episodesContainer.addEventListener('click', (event) => {
            const episodeCard = event.target.closest('.episode-selector');
            if (episodeCard) {
                event.preventDefault();
                handleEpisodeSelection(episodeCard, true);
            }
        });
    }

    if (translationSelectorPlaceholder) {
        translationSelectorPlaceholder.addEventListener('click', (event) => {
            const translationButton = event.target.closest('.translation-btn');
            if (translationButton) {
                event.preventDefault();
                const linkPk = translationButton.dataset.linkPk;
                const translationId = translationButton.dataset.translationId;

                if (linkPk) {
                    highlightTranslationButton(translationButton);
                    loadPlayer(linkPk, translationId);
                } else {
                    console.error("Translation button clicked but no link PK found.");
                }
            }
        });
    }


    if (nextEpisodeBtn) {
        nextEpisodeBtn.addEventListener('click', () => {
            const nextElement = findNextEpisodeElement(currentEpisodeElement);
            if (nextElement) {
                handleEpisodeSelection(nextElement, true);
            }
        });
    }

    if (prevEpisodeBtn) {
        prevEpisodeBtn.addEventListener('click', () => {
            const prevElement = findPrevEpisodeElement(currentEpisodeElement);
            if (prevElement) {
                handleEpisodeSelection(prevElement, true);
            }
        });
    }

    // Listener for detail tabs to save active state
    const detailTabs = document.querySelectorAll('#detail-tabs button[data-bs-toggle="tab"]');
    detailTabs.forEach(tabButton => {
        tabButton.addEventListener('shown.bs.tab', event => {
            if (lastDetailTabKey) {
                const activeTabTarget = event.target.getAttribute('data-bs-target'); // e.g. #details-pane or #watch-pane
                localStorage.setItem(lastDetailTabKey, activeTabTarget);
                console.log(`Saved active detail tab: ${activeTabTarget}`);
            }
        });
    });

    updateNavButtons();
    restoreLastDetailTab(); // Restore tab preference first
    restoreLastWatchedState(); // Then restore episode/translation

}); // End DOMContentLoaded