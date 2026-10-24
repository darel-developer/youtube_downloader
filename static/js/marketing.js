document.addEventListener('DOMContentLoaded', () => {
  const prompt = document.getElementById('prompt');
  const generateBtn = document.getElementById('generateBtn');
  const copyBtn = document.getElementById('copyBtn');
  const result = document.getElementById('result');

  if (!prompt || !generateBtn || !copyBtn || !result) return;

  function setLoading(isLoading) {
    generateBtn.disabled = isLoading;
    generateBtn.textContent = isLoading ? 'Génération...' : 'Générer la publication';
  }

  async function generatePost() {
    const text = prompt.value.trim();
    if (!text) {
      result.classList.remove('empty');
      result.textContent = 'Rédige un brief ou un sujet pour générer une publication performante.';
      return;
    }

    setLoading(true);
    result.classList.remove('empty');
    result.textContent = '⏳ Je prépare une publication optimisée pour votre audience...';

    try {
      const res = await fetch('/api/marketing/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Erreur inconnue');

      result.textContent = data.result;
    } catch (error) {
      result.textContent = '❌ ' + error.message;
    } finally {
      setLoading(false);
    }
  }

  generateBtn.addEventListener('click', generatePost);

  copyBtn.addEventListener('click', async () => {
    const text = result.textContent.trim();
    if (!text || result.classList.contains('empty')) return;

    try {
      await navigator.clipboard.writeText(text);
      copyBtn.textContent = 'Copié ✓';
      setTimeout(() => { copyBtn.textContent = 'Copier'; }, 1600);
    } catch (error) {
      copyBtn.textContent = 'Impossible';
    }
  });
});
