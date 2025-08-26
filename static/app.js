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

document.querySelectorAll(".delete-btn").forEach(btn => {
  btn.addEventListener("click", async (e) => {
      if (!confirm("Are you sure you want to delete this job?")) {
          return;
      }
      const id = e.target.getAttribute("data-id");
      try {
          await axios.delete(`/api/jobs/${id}/delete`);
          alert("Job deleted successfully!");
          window.location.reload();
      } catch (err) {
          alert("Failed to delete job. Please retry.");
      }
  });
});


document.getElementById("addJobForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const formData = new FormData(form);
  const data = Object.fromEntries(formData.entries());

  try {
      await axios.post("/add_job", data);
      alert("Job added successfully!");
      // Close the modal
      const modal = bootstrap.Modal.getInstance(document.getElementById('addJobModal'));
      if (modal) modal.hide();
      // Reload the page to show the new job
      window.location.reload();
  } catch (err) {
      alert("Failed to add job. Please retry.");
  }
});