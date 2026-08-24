import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { createMyTicket, listMyTickets } from "../api/portal";

const statusLabels: Record<string, string> = {
  open: "Abierto",
  in_progress: "En progreso",
  waiting_client: "Esperando tu respuesta",
  resolved: "Resuelto",
  closed: "Cerrado",
};

export default function Tickets() {
  const queryClient = useQueryClient();
  const { data: tickets = [] } = useQuery({ queryKey: ["my-tickets"], queryFn: listMyTickets });
  const [showForm, setShowForm] = useState(false);
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");

  const createMutation = useMutation({
    mutationFn: () => createMyTicket({ subject, description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-tickets"] });
      setSubject("");
      setDescription("");
      setShowForm(false);
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    createMutation.mutate();
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-800">Soporte</h1>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="text-sm text-blue-600 hover:underline"
        >
          {showForm ? "Cancelar" : "Nuevo ticket"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 space-y-2">
          <input
            required
            placeholder="Asunto"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full border rounded px-2 py-1.5 text-sm"
          />
          <textarea
            required
            rows={4}
            placeholder="Contanos qué está pasando"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full border rounded px-2 py-1.5 text-sm"
          />
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="w-full bg-slate-900 text-white text-sm rounded py-1.5 disabled:opacity-50"
          >
            Enviar
          </button>
        </form>
      )}

      <div className="space-y-2">
        {tickets.map((t) => (
          <Link
            key={t.id}
            to={`/tickets/${t.id}`}
            className="block bg-white rounded-lg shadow p-4 hover:bg-slate-50"
          >
            <p className="text-sm font-medium text-slate-800">{t.subject}</p>
            <p className="text-xs text-slate-400 mt-1">{statusLabels[t.status]}</p>
          </Link>
        ))}
        {tickets.length === 0 && (
          <p className="text-sm text-slate-400">Todavía no abriste ningún ticket.</p>
        )}
      </div>
    </div>
  );
}
