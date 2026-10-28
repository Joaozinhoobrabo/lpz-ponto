document.addEventListener("DOMContentLoaded", () => {
  const clock = document.querySelector("#live-clock");
  if (clock) {
    const updateClock = () => {
      clock.textContent = new Intl.DateTimeFormat("pt-BR", {
        hour: "2-digit", minute: "2-digit", second: "2-digit",
      }).format(new Date());
    };
    updateClock();
    window.setInterval(updateClock, 1000);
  }

  document.querySelectorAll("[data-punch-form]").forEach((form) => {
    let locationReady = false;
    form.addEventListener("submit", (event) => {
      if (locationReady) return;
      event.preventDefault();
      const submitter = event.submitter;
      const requireLocation = form.dataset.requireLocation === "true";
      const error = document.querySelector("#location-error");
      const setField = (name, value) => {
        form.elements.namedItem(name).value = value;
      };
      const finish = (status, reason, position) => {
        setField("location_status", status);
        setField("location_reason", reason);
        if (position) {
          setField("latitude", position.coords.latitude);
          setField("longitude", position.coords.longitude);
          setField("accuracy_meters", Math.round(position.coords.accuracy));
        }
        if (requireLocation && !position) {
          error.textContent = "A administração exige localização para esta marcação. Ative a permissão de localização e tente novamente.";
          error.hidden = false;
          submitter.disabled = false;
          return;
        }
        locationReady = true;
        form.requestSubmit(submitter);
      };

      error.hidden = true;
      submitter.disabled = true;
      if (!navigator.geolocation) {
        finish("unsupported", "Geolocalização não suportada pelo dispositivo");
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (position) => finish("captured", "", position),
        (geoError) => {
          const errors = {
            1: ["denied", "Permissão de localização negada"],
            2: ["unavailable", "Localização indisponível"],
            3: ["timeout", "Tempo esgotado ao obter localização"],
          };
          const [status, reason] = errors[geoError.code] || ["unavailable", "Não foi possível obter localização"];
          finish(status, reason);
        },
        { enableHighAccuracy: false, maximumAge: 0, timeout: 10000 },
      );
    });
  });
});