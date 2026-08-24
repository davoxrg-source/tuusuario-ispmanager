import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getMyTicket, listMyTicketReplies, replyToMyTicket } from "../api/portal";

const statusLabels: Record<string, string> = {
  open: "Abierto",
  in_progress: "En progreso",
  waiting_client: "Esperando tu respuesta",
  resolved: "Resuelto",
  closed: "Cerrado",
};

export default function TicketDetail() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const id = ticketId!;
  const queryClient = useQueryClient();
  const { data: ticket } = useQuery({ queryKey: ["my-ticket", id], queryFn: () => getMyTicket(id) });
  const { data: replies = [] } = useQuery({
    queryKey: ["my-ticket-replies", id],
    queryFn: () => listMyTicketReplies(id),
  });
  const [body, setBody] = useState("");

  const replyMutation = useMutation({
    mutationFn: () => replyToMyTicket(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-ticket-replies", id] });
      setBody("");
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    replyMutation.mutate();
  }

  if (!ticket) return <p className="text-sm text-slate-500">Cargando...</p>;

  return (
    <div className="space-y-3">
      <Link to="/tickets" className="text-xs text-blue-600 hover:underline">
        ← Volver
      </Link>
      <div className="bg-white rounded-lg shadow p-4">
        <h1 className="text-base font-semibold text-slate-800">{ticket.subject}</h1>
        <p className="text-xs text-slate-400 mt-1">{statusLabels[ticket.status]}</p>
        <p className="text-sm text-slate-600 mt-2 whitespace-pre-wrap">{ticket.description}</p>
      </div>

      <div className="space-y-2">
        {replies.map((r) => (
          <div
            key={r.id}
            className={`rounded-lg p-3 text-sm ${
              r.author_client_id ? "bg-blue-50 ml-8" : "bg-white shadow mr-8"
            }`}
          >
            <p className="text-xs text-slate-400 mb-1">{r.author_client_id ? "Vos" : "Soporte"}</p>
            <p className="whitespace-pre-wrap">{r.body}</p>
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          required
          placeholder="Escribí una respuesta..."
          value={body}
          onChange={(e) => setBody(e.target.value)}
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={replyMutation.isPending}
          className="bg-slate-900 text-white text-sm rounded px-4 disabled:opacity-50"
        >
          Enviar
        </button>
      </form>
    </div>
  );
}
