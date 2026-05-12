import { AgentEvent } from "../api/events";

type AgentTimelineProps = {
  events: AgentEvent[];
};

export function AgentTimeline({ events }: AgentTimelineProps) {
  return (
    <section>
      <h2>AgentTimeline</h2>
      {events.map((event) => (
        <div className="event" key={event.id}>
          <strong>{event.type}</strong>
          <pre>{JSON.stringify(event.payload, null, 2)}</pre>
        </div>
      ))}
    </section>
  );
}
