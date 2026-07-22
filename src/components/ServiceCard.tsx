import type { Service, ServiceStatus } from '../data/services';
import { CATEGORY_META } from '../data/services';
import { TypeIcon } from './Icons';

interface ServiceCardProps {
  service: Service;
  status: ServiceStatus;
}

function StatusBadge({ status }: { status: ServiceStatus }) {
  const labels: Record<ServiceStatus, string> = {
    online: 'Online',
    offline: 'Offline',
    unknown: 'Checking',
    cli: 'Local',
  };

  return (
    <span className={`status-badge ${status}`}>
      <span className={`status-dot ${status === 'online' ? 'pulse' : ''}`} />
      {labels[status]}
    </span>
  );
}

export function ServiceCard({ service, status }: ServiceCardProps) {
  const meta = CATEGORY_META[service.category];
  const isClickable = Boolean(service.url);
  const effectiveStatus: ServiceStatus =
    service.type === 'cli' || service.type === 'desktop' ? 'cli' : status;

  const handleClick = () => {
    if (service.url) window.open(service.url, '_blank', 'noopener,noreferrer');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <article
      className={`service-card ${isClickable ? 'clickable' : ''}`}
      style={{ '--accent': meta.color } as React.CSSProperties}
      onClick={isClickable ? handleClick : undefined}
      onKeyDown={isClickable ? handleKeyDown : undefined}
      role={isClickable ? 'link' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      title={service.url ?? `${service.project} — ${service.type}`}
    >
      <div className="service-card-top">
        <h4>{service.name}</h4>
        <StatusBadge status={effectiveStatus} />
      </div>
      <p>{service.description}</p>
      <div className="service-meta">
        <span className="service-type">
          <TypeIcon type={service.type} /> {service.type}
        </span>
        {service.port && <span className="service-port">:{service.port}</span>}
        <span className="service-type">{service.stack}</span>
      </div>
      <div className="service-tags">
        {service.tags.map((tag) => (
          <span key={tag} className="tag">
            {tag}
          </span>
        ))}
      </div>
    </article>
  );
}
