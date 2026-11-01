document.addEventListener("submit", (event) => {
  const cookie = document.cookie
    .split("; ")
    .find((value) => value.startsWith("csrftoken="));
  const tokenInput = event.target.elements?.namedItem("csrfmiddlewaretoken");
  if (!cookie || !tokenInput) return;

  tokenInput.value = decodeURIComponent(cookie.slice("csrftoken=".length));
}, true);
