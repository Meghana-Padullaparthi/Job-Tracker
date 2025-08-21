document.querySelectorAll(".applied-toggle").forEach(cb => {
    cb.addEventListener("change", async (e) => {
      const id = e.target.getAttribute("data-id");
      const applied = e.target.checked;
      try {
        await axios.post(`/api/jobs/${id}/applied`, { applied });
        const row = e.target.closest("tr");
        if (applied) row.classList.add("table-success");
        else row.classList.remove("table-success");
      } catch (err) {
        alert("Failed to update. Please retry.");
        e.target.checked = !applied;
      }
    });
  });
  