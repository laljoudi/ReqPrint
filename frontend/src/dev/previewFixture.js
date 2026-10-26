// DEV ONLY. Hardcoded sample data for the ?preview=... screens (see Preview.jsx), in the exact
// shape the backend returns: GeneratedRequirements for the document, ReviewResult for the review.
// Nothing in the app imports this except Preview.jsx, which main.jsx only loads when
// import.meta.env.DEV is true, so none of it ships in a production build.

// A string that exists nowhere else, so a grep of dist/ can prove this file was left out.
export const FIXTURE_MARKER = "reqprint-preview-fixture-7f3a9c";

export const PREVIEW_DESCRIPTION =
  "Project category: Software Systems\n\nA mobile and web app for ordering food from local restaurants. Customers browse menus, order, pay and track delivery; restaurants manage their menu and incoming orders.";

// A few turns of the interview, so the conversation panel looks like it does after one.
export const PREVIEW_QA = [
  { q: "Who will place orders, and who will fulfil them?", a: "Customers order; restaurant staff accept and prepare; our own couriers deliver." },
  { q: "How should customers pay?", a: "Card online, and cash on delivery in some areas." },
  { q: "What should happen if a restaurant can't make an order?", a: "The customer is told straight away and refunded in full." },
];

export const PREVIEW_DATA = {
  requirements: {
    functional: [
      "The system shall let a customer browse restaurants near their delivery address, filtered by cuisine, rating and delivery time.",
      "The system shall let a customer add menu items, with options and notes, to a basket and review it before ordering.",
      "The system shall accept payment by card online and record cash-on-delivery orders as unpaid until delivery.",
      "The system shall notify a restaurant of a new order within 5 seconds of payment being confirmed.",
      "The system shall let restaurant staff accept, reject or mark an order as ready, and shall tell the customer each time.",
      "The system shall let a customer track the courier's live position from pickup to delivery.",
      "The system shall refund the full amount automatically when a restaurant rejects an order.",
      "The system shall let restaurant managers edit menu items, prices and availability without a release.",
    ],
    non_functional: [
      "Search results shall load in under 2 seconds at the 95th percentile for up to 5,000 concurrent users.",
      "Card details shall never be stored by the system; payments shall go through a PCI DSS compliant provider.",
      "The customer app shall be usable on the two most recent major versions of iOS and Android and on current desktop browsers.",
      "The service shall be available 99.5% of each month, measured outside planned maintenance windows.",
      "All personal data shall be stored encrypted at rest and removed within 30 days of an account deletion request.",
    ],
  },
  user_stories: [
    { id: "US-01", role: "Customer", story: "As a customer, I want to search restaurants by cuisine and delivery time, so that I can quickly find something I'll enjoy." },
    { id: "US-02", role: "Customer", story: "As a customer, I want to customise a dish and add it to my basket, so that my order matches what I actually want." },
    { id: "US-03", role: "Customer", story: "As a customer, I want to pay by card or choose cash on delivery, so that I can use the method that suits me." },
    { id: "US-04", role: "Restaurant staff", story: "As restaurant staff, I want to accept or reject incoming orders, so that I only commit to what the kitchen can make." },
    { id: "US-05", role: "Courier", story: "As a courier, I want to see the pickup and drop-off addresses for my delivery, so that I can complete it without calling anyone." },
    { id: "US-06", role: "Restaurant manager", story: "As a restaurant manager, I want to mark a dish as sold out, so that customers can't order it." },
  ],
  acceptance_criteria: [
    { story_id: "US-01", scenario: "Filter by cuisine", given: "a customer has set a delivery address", when: "they choose the cuisine Thai", then: "only restaurants serving Thai food that deliver to that address are listed" },
    { story_id: "US-01", scenario: "No matches", given: "no restaurant matches the chosen filters", when: "the results load", then: "a message suggests removing a filter instead of showing an empty list" },
    { story_id: "US-02", scenario: "Required option missing", given: "a dish has a required size option", when: "the customer taps Add without choosing a size", then: "the dish is not added and the size option is highlighted" },
    { story_id: "US-02", scenario: "Add with a note", given: "a customer is viewing a dish", when: "they add a note and tap Add", then: "the basket shows the dish with that note" },
    { story_id: "US-03", scenario: "Successful card payment", given: "a basket totalling 24.50 and a valid card", when: "the customer confirms payment", then: "the order is created as paid and a receipt is emailed" },
    { story_id: "US-03", scenario: "Declined card", given: "a card the provider declines", when: "the customer confirms payment", then: "no order is created and the customer is asked to try another method" },
    { story_id: "US-04", scenario: "Reject an order", given: "a new order is waiting for the restaurant", when: "staff reject it and choose a reason", then: "the customer is notified and refunded in full" },
    { story_id: "US-04", scenario: "Order not answered", given: "a new order has waited 3 minutes without a response", when: "the timer expires", then: "the order is cancelled and the customer is refunded" },
    { story_id: "US-05", scenario: "Assigned delivery", given: "an order marked ready for pickup", when: "a courier accepts the delivery", then: "both addresses and the customer's phone number are shown" },
    { story_id: "US-06", scenario: "Sold out dish", given: "a dish is marked as sold out", when: "a customer views the menu", then: "the dish is shown as unavailable and cannot be added" },
  ],
  use_cases: [
    {
      use_case_id: "UC-01 Place an order",
      actors: "Customer, Payment provider, Restaurant staff",
      description: "A customer chooses dishes from one restaurant, pays, and the restaurant receives the order.",
      preconditions: "The customer is signed in and has a delivery address inside the restaurant's delivery area.",
      trigger: "The customer taps Checkout on a non-empty basket.",
      main_flow: "1. The system shows the order summary and total. 2. The customer chooses a payment method. 3. The payment provider confirms payment. 4. The system creates the order and notifies the restaurant. 5. The customer sees the order status screen.",
      alternative_flow: "3a. Payment is declined: the system keeps the basket and asks for another method. 4a. The restaurant is closed: the system blocks checkout and explains when it reopens.",
    },
    {
      use_case_id: "UC-02 Reject an order",
      actors: "Restaurant staff, Customer",
      description: "Restaurant staff decline an order they cannot prepare and the customer is refunded.",
      preconditions: "An order has been paid and is awaiting a response from the restaurant.",
      trigger: "Staff select Reject on the order.",
      main_flow: "1. Staff choose a reason. 2. The system cancels the order. 3. The system refunds the full amount. 4. The system notifies the customer with the reason.",
      alternative_flow: "3a. The refund fails: the system flags the order for support and tells the customer a refund is being processed.",
    },
  ],
  assumptions: [
    "Restaurants have a tablet or phone available to receive orders during opening hours.",
    "Couriers are employed or contracted by the company; courier recruitment and payroll are out of scope.",
    "Prices are shown in a single currency per country; multi-currency baskets are not needed.",
    "Customer support is handled in an existing helpdesk tool, outside this system.",
  ],
};

// At least two issues per severity, and all three roles at every severity.
export const PREVIEW_REVIEW = {
  issues: [
    {
      role: "Business Analyst", severity: "high",
      issue: "Cash on delivery has no rule for failed or refused deliveries",
      why_it_matters: "Without a rule, the business absorbs the cost of food that was prepared but never paid for, and couriers have no guidance at the door.",
      suggested_fix: "Specify what happens when cash is refused or no one answers: how long the courier waits, who is told, and whether the customer is blocked from cash orders afterwards.",
    },
    {
      role: "Developer", severity: "high",
      issue: "Refund behaviour for a payment that is still pending is undefined",
      why_it_matters: "If a restaurant rejects an order while the card payment is still settling, the system may refund money it has not yet received, or never refund it.",
      suggested_fix: "State the order and payment states explicitly and define the allowed transitions, including rejection during a pending payment.",
    },
    {
      role: "QA Tester", severity: "high",
      issue: "The 5-second restaurant notification target cannot be verified",
      why_it_matters: "The requirement gives no start or end point and no load condition, so two testers could pass and fail the same build.",
      suggested_fix: "Define it as the time from the payment provider's confirmation to the notification appearing on the restaurant device, measured at the 95th percentile under the stated concurrent load.",
    },
    {
      role: "Business Analyst", severity: "medium",
      issue: "Delivery area is mentioned but never defined",
      why_it_matters: "Several stories depend on 'inside the delivery area', yet nothing says whether it is a radius, a polygon or a postcode list, or who maintains it.",
      suggested_fix: "Add a requirement for how restaurants define their delivery area and how an address is checked against it.",
    },
    {
      role: "Developer", severity: "medium",
      issue: "Live courier tracking has no stated update frequency or battery constraint",
      why_it_matters: "Position updates drive both server cost and courier battery life, and a fixed interval will be chosen implicitly if none is specified.",
      suggested_fix: "Specify an update interval (for example every 5 seconds while moving) and what the customer sees when updates stop.",
    },
    {
      role: "QA Tester", severity: "medium",
      issue: "'Usable' on iOS, Android and desktop browsers is not testable",
      why_it_matters: "The non-functional requirement names platforms but no device list, browser versions or usability criteria to test against.",
      suggested_fix: "List the minimum supported OS and browser versions and the core journeys that must pass on each.",
    },
    {
      role: "Business Analyst", severity: "low",
      issue: "Order history and re-ordering are not covered",
      why_it_matters: "Customers who order repeatedly usually expect to repeat a past order, which is cheap to add early and awkward to retrofit.",
      suggested_fix: "Decide whether order history is in scope for the first release and add a story if it is.",
    },
    {
      role: "Developer", severity: "low",
      issue: "Menu edits 'without a release' do not say how quickly they reach customers",
      why_it_matters: "Cached menus can show a dish that has just sold out, which then contradicts the sold-out acceptance criterion.",
      suggested_fix: "State a maximum delay for a menu change to appear, for example 60 seconds.",
    },
    {
      role: "QA Tester", severity: "low",
      issue: "The 'No matches' message in US-01 has no wording or example",
      why_it_matters: "Testers can confirm a message appears but not that it suggests something useful, so the criterion is only half checkable.",
      suggested_fix: "Add the expected message text, or an example, to the acceptance criterion.",
    },
  ],
};
