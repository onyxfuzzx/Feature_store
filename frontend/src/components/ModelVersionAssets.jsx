import { useRef, useState } from "react";
import { fetchAllApi, fetchApi } from "../api";
import { Button } from "./ui/Button";
import { Modal } from "./ui/Modal";

export default function ModelVersionAssets({
  model,
  version,
  canEdit,
  canLink,
  onChanged,
}) {
  const file = useRef(null);
  const [error, setError] = useState(null),
    [busy, setBusy] = useState(false),
    [open, setOpen] = useState(false);
  const [features, setFeatures] = useState([]),
    [selected, setSelected] = useState([]),
    [dataset, setDataset] = useState("");
  const endpoint = `/models/${model.id}/versions/${version.id}/artifact`;
  const upload = async (event) => {
    const chosen = event.target.files[0];
    if (!chosen) return;
    setBusy(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", chosen);
      await fetchApi(endpoint, { method: "POST", body });
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      if (file.current) file.current.value = "";
    }
  };
  const download = async () => {
    try {
      setError(null);
      const blob = await fetchApi(endpoint, { responseType: "blob" });
      const url = URL.createObjectURL(blob),
        anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `model-${version.version}.bin`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err.message);
    }
  };
  const edit = async () => {
    try {
      setError(null);
      const [all, groups, links] = await Promise.all([
        fetchAllApi("/features"),
        fetchAllApi("/features/groups"),
        fetchApi(`/models/versions/${version.id}/lineage`),
      ]);
      const allowed = new Set(
        groups
          .filter((group) => group.environment === model.environment)
          .map((group) => group.id),
      );
      setFeatures(all.filter((feature) => allowed.has(feature.group_id)));
      setSelected(
        links.flatMap((link) => JSON.parse(link.feature_ids_json || "[]")),
      );
      setDataset(links[0]?.dataset_uri || "");
      setOpen(true);
    } catch (err) {
      setError(err.message);
    }
  };
  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await fetchApi(`/models/versions/${version.id}/lineage`, {
        method: "POST",
        body: JSON.stringify({
          feature_ids_json: JSON.stringify(selected),
          dataset_uri: dataset || null,
        }),
      });
      setOpen(false);
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="inline-flex flex-wrap gap-2 justify-end">
      {canEdit && (
        <>
          <input
            ref={file}
            type="file"
            className="sr-only"
            aria-label={`Upload artifact v${version.version}`}
            onChange={upload}
          />
          <Button size="sm" onClick={() => file.current.click()} loading={busy}>
            Upload Artifact
          </Button>
        </>
      )}
      {version.artifact_uri && (
        <Button size="sm" onClick={download}>
          Download Artifact
        </Button>
      )}
      {canLink && (
        <Button size="sm" onClick={edit}>
          Link Features
        </Button>
      )}
      {error && (
        <p role="alert" className="w-full text-rose-300">
          {error}
        </p>
      )}
      <Modal
        isOpen={open}
        title={`Training Features - v${version.version}`}
        onClose={() => setOpen(false)}
      >
        <form onSubmit={save} className="space-y-4">
          <fieldset>
            <legend>Features in {model.environment}</legend>
            {features.map((feature) => (
              <label key={feature.id} className="block text-sm py-1">
                <input
                  type="checkbox"
                  checked={selected.includes(feature.id)}
                  onChange={(event) =>
                    setSelected(
                      event.target.checked
                        ? [...selected, feature.id]
                        : selected.filter((id) => id !== feature.id),
                    )
                  }
                />{" "}
                {feature.name}
              </label>
            ))}
          </fieldset>
          <label>
            Training dataset URI
            <input
              aria-label="Training dataset URI"
              className="block w-full bg-zinc-950 p-2"
              value={dataset}
              onChange={(e) => setDataset(e.target.value)}
            />
          </label>
          <Button type="submit" loading={busy}>
            Save Training Features
          </Button>
        </form>
      </Modal>
    </div>
  );
}
