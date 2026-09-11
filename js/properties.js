/* ==================================================
   EDIT PROPERTY LISTINGS HERE
   ==================================================
   ADD: copy an object and give it a unique id. REMOVE: delete its object.
   IMAGE: replace image with a stable URL/relative path. CATEGORY: use plot,
   flat, luxury, commercial, or villa so the filters continue to work. */
const PROPERTIES = [
  {id:1,name:"Premium Freehold Plot",type:"plot",label:"Plot",location:"Sector XX, Noida",image:"https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1400&q=80",description:"A sample land opportunity presented for enquiry and independent verification."},
  {id:2,name:"Contemporary City Residence",type:"flat",label:"Flat",location:"Greater Noida",image:"https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1400&q=80",description:"A demo residential listing for buyers exploring modern urban living."},
  {id:3,name:"Signature Apartment",type:"luxury",label:"Luxury",location:"Noida",image:"https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1400&q=80",description:"A sample premium home listing. Specifications are available on enquiry."},
  {id:4,name:"Commercial Address",type:"commercial",label:"Commercial",location:"Noida Extension",image:"https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1400&q=80",description:"A demo commercial opportunity for businesses and investors to explore."},
  {id:5,name:"Garden Villa",type:"villa",label:"Villa",location:"Greater Noida",image:"https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1400&q=80",description:"A sample villa listing designed to illustrate the property portfolio."},
  {id:6,name:"Connected Residential Plot",type:"plot",label:"Plot",location:"Yamuna Expressway region",image:"https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=1400&q=80",description:"A demo plot listing. Contact the team for current and verified information."}
];
window.PROPERTIES = PROPERTIES;

function propertyCard(p) {
  return `<article class="property-card reveal" data-type="${p.type}"><a href="properties.html?id=${p.id}" aria-label="View ${p.name}"><div class="property-image"><img src="${p.image}" alt="Sample imagery for ${p.name}" loading="lazy"><span class="demo-tag">DEMO LISTING</span></div><div class="property-copy"><div><span class="eyebrow">${p.label} · ${p.location}</span><h3>${p.name}</h3></div><span class="circle-arrow" aria-hidden="true">↗</span><p>${p.description}</p><strong>Contact for details</strong></div></a></article>`;
}

function renderProperties() {
  const grid = document.querySelector("[data-property-grid]");
  if (!grid) return;
  const detailId = Number(new URLSearchParams(location.search).get("id"));
  const detail = document.querySelector("[data-property-detail]");
  if (detail && detailId) {
    const p = PROPERTIES.find(item => item.id === detailId);
    if (p) detail.innerHTML = `<div class="detail-image"><img src="${p.image}" alt="Sample imagery for ${p.name}"></div><div><span class="eyebrow">DEMO LISTING · ${p.label}</span><h1>${p.name}</h1><p class="lead">${p.location}</p><p>${p.description}</p><div class="notice">Details, availability, ownership documentation, approvals and pricing must be independently verified before any decision.</div><a class="btn btn-gold" href="contact.html?interest=${encodeURIComponent(p.name)}">Enquire now <span>↗</span></a></div>`;
    detail.hidden = false; document.querySelector(".properties-browser")?.setAttribute("hidden", ""); return;
  }
  const draw = (filter="all", query="") => {
    const matches = PROPERTIES.filter(p => (filter === "all" || p.type === filter) && `${p.name} ${p.location}`.toLowerCase().includes(query.toLowerCase()));
    grid.innerHTML = matches.map(propertyCard).join("") || `<p class="empty">No sample listings match your search.</p>`;
  };
  const initialFilter = new URLSearchParams(location.search).get("filter");
  if (initialFilter && document.querySelector(`[data-filter="${initialFilter}"]`)) {
    document.querySelectorAll("[data-filter]").forEach(b => b.classList.toggle("active", b.dataset.filter === initialFilter));
    draw(initialFilter);
  } else draw();
  document.querySelectorAll("[data-filter]").forEach(btn => btn.addEventListener("click", () => {document.querySelectorAll("[data-filter]").forEach(b=>b.classList.remove("active"));btn.classList.add("active");draw(btn.dataset.filter, document.querySelector("[data-property-search]")?.value || "");}));
  document.querySelector("[data-property-search]")?.addEventListener("input", e => draw(document.querySelector("[data-filter].active")?.dataset.filter || "all", e.target.value));
}
document.addEventListener("DOMContentLoaded", renderProperties);
