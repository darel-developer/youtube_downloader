document.addEventListener('DOMContentLoaded', () => {
    const summaryBtn = document.getElementById('summarizeBtn');
    const downloadForm = document.getElementById('dlForm');
    const statusEl = document.getElementById('status');
    const statusMessage = document.getElementById('statusMessage');
    const summaryCard = document.getElementById('summaryCard');
    const summaryText = document.getElementById('summaryText');

    function setStatus(message, isError = false) {
        statusEl.classList.remove('d-none');
        statusMessage.textContent = message;
        statusEl.style.borderColor = isError ? 'rgba(220, 53, 69, 0.3)' : 'rgba(0, 123, 255, 0.3)';
        statusEl.style.backgroundColor = isError ? 'rgba(255, 230, 230, 0.85)' : 'rgba(226, 241, 255, 0.85)';
    }

    function clearStatus() {
        statusEl.classList.add('d-none');
        statusMessage.textContent = '';
    }

    function showSummary(text) {
        summaryText.textContent = text;
        summaryCard.classList.remove('d-none');
    }

    function hideSummary() {
        summaryCard.classList.add('d-none');
        summaryText.textContent = '';
    }

    function disableForm(disabled) {
        downloadForm.querySelectorAll('button, input, select').forEach(el => {
            el.disabled = disabled;
        });
    }

    function getFilenameFromDisposition(disposition) {
        if (!disposition) return null;
        const match = /filename\*?=(?:UTF-8''?)?"?([^";]+)"?/.exec(disposition);
        return match ? decodeURIComponent(match[1]) : null;
    }

    async function fetchSummary() {
        const url = document.getElementById('url').value.trim();
        if (!url) {
            setStatus('Veuillez entrer une URL YouTube.', true);
            return;
        }

        clearStatus();
        hideSummary();
        setStatus('Génération du résumé…');
        summaryBtn.disabled = true;
        disableForm(true);

        try {
            const response = await fetch('/api/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || `Erreur ${response.status}`);
            }

            showSummary(data.summary);
            setStatus('Résumé généré avec succès ✅');
        } catch (error) {
            setStatus(`Erreur : ${error.message}`, true);
        } finally {
            summaryBtn.disabled = false;
            disableForm(false);
        }
    }

    async function handleDownload(event) {
        event.preventDefault();

        const url = document.getElementById('url').value.trim();
        const format = document.getElementById('format').value;

        if (!url) {
            setStatus('Veuillez entrer une URL YouTube.', true);
            return;
        }

        clearStatus();
        hideSummary();
        setStatus('Téléchargement en cours…');
        disableForm(true);

        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, format })
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || `Erreur ${response.status}`);
            }

            const blob = await response.blob();
            const disposition = response.headers.get('Content-Disposition');
            const filename = getFilenameFromDisposition(disposition) || `download.${format}`;
            const link = document.createElement('a');
            const objectUrl = URL.createObjectURL(blob);

            link.href = objectUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(objectUrl);

            setStatus('Téléchargement prêt ! ✅');
        } catch (error) {
            setStatus(`Erreur : ${error.message}`, true);
        } finally {
            disableForm(false);
        }
    }

    summaryBtn.addEventListener('click', (event) => {
        event.preventDefault();
        fetchSummary();
    });

    downloadForm.addEventListener('submit', handleDownload);
});
