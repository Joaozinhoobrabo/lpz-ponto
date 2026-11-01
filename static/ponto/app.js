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

  const faceDialog = document.querySelector("#face-dialog");
  const video = document.querySelector("#face-video");
  const captureButton = faceDialog?.querySelector("[data-face-capture]");
  const cancelButton = faceDialog?.querySelector("[data-face-cancel]");

  const captureFace = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Este navegador não permite acessar a câmera. Use HTTPS ou localhost.");
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false,
    });

    try {
      video.srcObject = stream;
      await video.play();
      faceDialog.showModal();

      return await new Promise((resolve, reject) => {
        const cleanup = () => {
          captureButton.removeEventListener("click", capture);
          cancelButton.removeEventListener("click", cancel);
          faceDialog.removeEventListener("cancel", onCancel);
        };
        const cancel = () => {
          cleanup();
          faceDialog.close();
          reject(new Error("Validação facial cancelada."));
        };
        const onCancel = (event) => {
          event.preventDefault();
          cleanup();
          faceDialog.close();
          reject(new Error("Validação facial cancelada."));
        };
        const capture = () => {
          const canvas = document.createElement("canvas");
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          const context = canvas.getContext("2d");
          if (!context || !canvas.width || !canvas.height) {
            cleanup();
            faceDialog.close();
            reject(new Error("Não foi possível capturar a imagem da câmera."));
            return;
          }
          context.drawImage(video, 0, 0, canvas.width, canvas.height);
          canvas.toBlob((blob) => {
            cleanup();
            faceDialog.close();
            if (blob) {
              resolve(blob);
            } else {
              reject(new Error("Não foi possível preparar a imagem da câmera."));
            }
          }, "image/jpeg", 0.9);
        };

        captureButton.addEventListener("click", capture);
        cancelButton.addEventListener("click", cancel);
        faceDialog.addEventListener("cancel", onCancel);
      });
    } finally {
      stream.getTracks().forEach((track) => track.stop());
      video.srcObject = null;
      if (faceDialog.open) faceDialog.close();
    }
  };

  const captureLocation = (form) => new Promise((resolve, reject) => {
    const requireLocation = form.dataset.requireLocation === "true";
    const setField = (name, value) => {
      const field = form.elements.namedItem(name);
      if (field) field.value = value;
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
        reject(new Error("A localização é obrigatória. Ative a permissão de localização e tente novamente."));
        return;
      }
      resolve();
    };

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

  document.querySelectorAll("[data-punch-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitter = event.submitter || form.querySelector('button[type="submit"]');
      const error = document.querySelector("#location-error");
      const note = document.querySelector("#location-message");
      if (!submitter || !error || !note) return;
      error.hidden = true;
      error.textContent = "";
      submitter.disabled = true;
      note.textContent = "Obtendo localização e iniciando a câmera...";

      try {
        await captureLocation(form);
        const image = await captureFace();
        note.textContent = "Validando biometria e registrando a marcação...";

        const payload = new FormData(form);
        payload.append("foto", image, "captura-facial.jpg");
        const response = await fetch(form.dataset.faceEndpoint, {
          method: "POST",
          body: payload,
          credentials: "same-origin",
        });

        let result;
        try {
          result = await response.json();
        } catch {
          throw new Error("O servidor retornou uma resposta inválida. Tente novamente.");
        }
        if (!response.ok) {
          throw new Error(result.detail || "Não foi possível validar o rosto.");
        }
        window.location.reload();
      } catch (requestError) {
        error.textContent = requestError.message || "Não foi possível registrar o ponto.";
        error.hidden = false;
        note.textContent = "A validação facial é necessária para registrar o ponto.";
        submitter.disabled = false;
      }
    });
  });
});
