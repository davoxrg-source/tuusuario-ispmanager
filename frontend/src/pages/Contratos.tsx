import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  createContract,
  createContractTemplate,
  deleteContractTemplate,
  listContractTemplates,
  listContracts,
  voidContract,
} from "../api/contracts";
import { listClients } from "../api/clients";
import { fetchCurrentUser } from "../api/auth";
import type { ContractStatus, ContractTemplateInput } from "../api/types";
import Field from "../components/Field";

const emptyTemplateForm: ContractTemplateInput = { name: "", body: "" };

const statusLabels: Record<ContractStatus, string> = {
  draft: "Borrador",
  signed: "Firmado",
  void: "Anulado",
};

const statusStyles: Record<ContractStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  signed: "bg-green-100 text-green-700",
  void: "bg-red-100 text-red-700",
};

export default function Contratos() {
  const queryClient = useQueryClient();
  const { data: contracts = [] } = useQuery({ queryKey: ["contracts"], queryFn: listContracts });
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });
  const { data: templates = [] } = useQuery({
    queryKey: ["contract-templates"],
    queryFn: listContractTemplates,
  });
  const { data: currentUser } = useQuery({ queryKey: ["me"], queryFn: fetchCurrentUser });

  const [newClientId, setNewClientId] = useState("");
  const [newTemplateId, setNewTemplateId] = useState("");
  const [showTemplateForm, setShowTemplateForm] = useState(false);
  const [templateForm, setTemplateForm] = useState<ContractTemplateInput>(emptyTemplateForm);

  const createContractMutation = useMutation({
    mutationFn: createContract,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contracts"] });
      setNewClientId("");
      setNewTemplateId("");
    },
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo crear el contrato."),
  });

  const voidMutation = useMutation({
    mutationFn: voidContract,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contracts"] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo anular el contrato."),
  });

  const createTemplateMutation = useMutation({
    mutationFn: createContractTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contract-templates"] });
      setTemplateForm(emptyTemplateForm);
      setShowTemplateForm(false);
    },
  });

  const deleteTemplateMutation = useMutation({
    mutationFn: deleteContractTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contract-templates"] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo borrar la plantilla."),
  });

  function handleNewContract(e: FormEvent) {
    e.preventDefault();
    createContractMutation.mutate({ client_id: newClientId, template_id: newTemplateId });
  }

  function handleTemplateSubmit(e: FormEvent) {
    e.preventDefault();
    createTemplateMutation.mutate(templateForm);
  }

  function clientName(id: string | null) {
    return clients.find((c) => c.id === id)?.full_name ?? "—";
  }

  function templateName(id: string | null) {
    return templates.find((t) => t.id === id)?.name ?? "—";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Contratos</h1>

      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-medium text-slate-600 mb-3">Nuevo contrato</h2>
        <form onSubmit={handleNewContract} className="grid grid-cols-3 gap-3">
          <select
            required
            value={newClientId}
            onChange={(e) => setNewClientId(e.target.value)}
            className="border rounded px-3 py-2 text-sm bg-white"
          >
            <option value="">Cliente...</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.full_name}
              </option>
            ))}
          </select>
          <select
            required
            value={newTemplateId}
            onChange={(e) => setNewTemplateId(e.target.value)}
            className="border rounded px-3 py-2 text-sm bg-white"
          >
            <option value="">Plantilla...</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={createContractMutation.isPending}
            className="bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            Crear borrador
          </button>
        </form>
        {templates.length === 0 && (
          <p className="text-xs text-slate-400 mt-2">
            Todavía no hay plantillas — creá una abajo antes de armar un contrato.
          </p>
        )}
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2">Cliente</th>
              <th className="px-4 py-2">Plantilla</th>
              <th className="px-4 py-2">Estado</th>
              <th className="px-4 py-2">Firmado</th>
              <th className="px-4 py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {contracts.map((contract) => (
              <tr key={contract.id} className="border-t">
                <td className="px-4 py-2">{clientName(contract.client_id)}</td>
                <td className="px-4 py-2">{templateName(contract.template_id)}</td>
                <td className="px-4 py-2">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${statusStyles[contract.status]}`}>
                    {statusLabels[contract.status]}
                  </span>
                </td>
                <td className="px-4 py-2 text-slate-500">
                  {contract.signed_at ? new Date(contract.signed_at).toLocaleString() : "—"}
                </td>
                <td className="px-4 py-2 space-x-2">
                  <Link
                    to={`/contratos/${contract.id}/firmar`}
                    target="_blank"
                    className="text-xs text-blue-600 hover:underline"
                  >
                    {contract.status === "draft" ? "Firmar" : "Ver"}
                  </Link>
                  {contract.status === "signed" && currentUser?.role === "admin" && (
                    <button
                      onClick={() => voidMutation.mutate(contract.id)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Anular
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {contracts.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  Aún no hay contratos.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {currentUser?.role === "admin" && (
        <div className="bg-white rounded-lg shadow p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-slate-600">Plantillas de contrato</h2>
            <button
              onClick={() => setShowTemplateForm((s) => !s)}
              className="text-xs text-blue-600 hover:underline"
            >
              {showTemplateForm ? "Cancelar" : "Nueva plantilla"}
            </button>
          </div>
          {showTemplateForm && (
            <form onSubmit={handleTemplateSubmit} className="space-y-3 mb-4">
              <Field label="Nombre">
                <input
                  required
                  value={templateForm.name}
                  onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                  className="border rounded px-3 py-2 text-sm w-full"
                />
              </Field>
              <Field
                label="Texto del contrato"
                hint="Placeholders disponibles: {full_name} {identification} {address} {phone} {email} {plan_name} {plan_price} {today}"
              >
                <textarea
                  required
                  rows={8}
                  value={templateForm.body}
                  onChange={(e) => setTemplateForm({ ...templateForm, body: e.target.value })}
                  className="border rounded px-3 py-2 text-sm w-full font-mono"
                />
              </Field>
              <button
                type="submit"
                disabled={createTemplateMutation.isPending}
                className="bg-slate-900 text-white text-sm rounded px-4 py-2 disabled:opacity-50"
              >
                Guardar plantilla
              </button>
            </form>
          )}
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-1">Nombre</th>
                <th className="py-1"></th>
              </tr>
            </thead>
            <tbody>
              {templates.map((t) => (
                <tr key={t.id} className="border-t">
                  <td className="py-1">{t.name}</td>
                  <td className="py-1">
                    <button
                      onClick={() => deleteTemplateMutation.mutate(t.id)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
              {templates.length === 0 && (
                <tr>
                  <td colSpan={2} className="py-4 text-center text-slate-400">
                    Aún no hay plantillas.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function axiosErrorMessage(err: unknown): string | null {
  if (typeof err === "object" && err !== null && "response" in err) {
    const response = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}
