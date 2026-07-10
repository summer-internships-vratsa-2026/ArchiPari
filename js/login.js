(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("loginForm");
    const status = document.getElementById("formStatus");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const email = form.email.value.trim();
      const password = form.password.value;

      status.textContent = "Влизане…";
      status.className = "form-status show";

      const { error } = await window.ArchiPariAuth.client.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        status.textContent = "Грешка: " + (
          error.message === "Invalid login credentials"
            ? "Грешен имейл или парола."
            : error.message
        );
        status.className = "form-status show error";
        return;
      }

      status.textContent = "Успешен вход! Пренасочваме те…";
      status.className = "form-status show ok";

      const params = new URLSearchParams(window.location.search);
      const redirect = params.get("redirect") || "contact.html";
      setTimeout(() => {
        window.location.href = redirect;
      }, 500);
    });
  });
})();
