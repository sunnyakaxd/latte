frappe.provide('latte.kafka_queue_monitor');

async function get_kafka_queue_bootstrap_server() {
	const { message } = await frappe.call('latte.latte_core.page.kafka_queue_monitor.get_bootstrap_server');
	return message;
}

frappe.pages['kafka-queue-monitor'].on_page_load = async function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Kafka Queue Monitor',
		single_column: true
	});
	page.bootstrap_server = page.add_field({
		fieldname: 'bootstrap_server',
		label: __('Bootstrap Server'),
		fieldtype: 'Data',
		reqd: 1,
		default: await get_kafka_queue_bootstrap_server(),
		change() {
			if (this.value !== this.previous_value) {
				page.monitor.reload();
			}
			this.previous_value = this.value;
		},
	});
	page.refresh_button = page.add_field({
		fieldname: 'Refresh',
		label: __('Refresh'),
		fieldtype: 'Button',
		click: () => {
			page.monitor.reload();
		},
	});
	page.monitor = new latte.kafka_queue_monitor.Monitor(wrapper, page);
}
latte.kafka_queue_monitor.Monitor = class Monitor {
	constructor(wrapper, page) {
		this.wrapper = $(wrapper);
		// this.add_buttons();
		this.page = page;
		this.reload();
	}

	reload() {
		this.refresh_data().then(() => {
			this.enable_events();
		})
	}

	load_wrapper() {
		$('#page-kafka-queue-monitor').find('.container.page-body').removeClass('container');
		$(this.wrapper).find('.kafka-ui-container').remove();
		this.wrapper.find('.layout-main').append(`
		<div class="container-fluid kafka-ui-container">
			<div class="row">
				<div class="topic-list col-md-4">
					<div class="topic-list-container col-md-12">
						<h2> Topics </h2>
					</div>
				</div>
				<div class="cg-list col-md-4">
					<div class="cg-list-container col-md-12">
						<h2> Consumer Groups </h2>
					</div>
				</div>
				<div class="consumer-list col-md-4">
					<div class="consumer-list-redis col-md-12">
						<h2> Consumer Names </h2>
					</div>
				</div>
				<style>
					.topic-meta {
						padding:0px 35px 50px;
					}
					table {
						font-family: Arial, "Helvetica Neue", Helvetica, sans-serif;
						border-collapse: collapse;
						width: 100%;
						font-size: 14px;
						border: 1px solid #ccc;
					}
					th, td {
						text-align: center;
						border: 1px solid #ccc;
					}
				</style>
				<div class="topic-meta col-md-12">
					<h2 id="meta-name"></h2>
					<table><tbody id="meta-table"></tbody></table>
				</div>
			</div>
		</div>
		`);
	}

	async refresh_data() {
		const bootstrap_server = this.page.bootstrap_server.get_value();
		const topics = await frappe.xcall('latte.latte_core.page.kafka_queue_monitor.get_topics', {
			bootstrap_server
		});
		const cg_list = await frappe.xcall('latte.latte_core.page.kafka_queue_monitor.get_consumer_groups', {
			bootstrap_server
		});
		const active_consumers = await frappe.xcall('latte.latte_core.page.kafka_queue_monitor.get_smembers');
		this.load_wrapper();
		this.wrapper.find('.topic-list-container').append(`
			<ol style="list-style-type:disc;">
				${topics.map(topic => `<li class="topic-name" topic-name="${topic}">${topic}</li>`).join('\n')}
			</ol>
		`);
		this.wrapper.find('.cg-list-container').append(`
			<ol style="list-style-type:disc;">
				${cg_list.map(cg => `<li class="cg-name" cg-name="${cg}">${cg}</li>`).join('\n')}
			</ol>
		`);
		this.wrapper.find('.consumer-list-redis').append(`
			<ol style="list-style-type:disc;">
				${Object.values(active_consumers).map(cons => `
					<li class="consumer-name" style="font-weight: ${cons.leader?'bold':'normal'}" consumer-name="${cons.name}">
						${cons.name} (${cons.queue})
					</li>
				`).join('\n')}
			</ol>
		`);
	}

	enable_events() {
		this.wrapper.find('.topic-name').click((event) => {
			const topic_name = event.target.attributes['topic-name'].value;
			console.log(topic_name);
			this.load_topic_meta(topic_name);
		});

		this.wrapper.find('.cg-name').click((event) => {
			const cg_name = event.target.attributes['cg-name'].value;
			console.log(cg_name);
			this.load_cg_meta(cg_name);
		});

		this.wrapper.find('.consumer-name').click((event) => {
			const consumer_name = event.target.attributes['consumer-name'].value;
			console.log(consumer_name);
			this.load_consumer_meta(consumer_name);
		});
	}

	async load_topic_meta(topic) {
		const bootstrap_server = this.page.bootstrap_server.get_value();
		this.wrapper.find('#meta-name').html(`Topic Meta - ${topic}`);
		this.wrapper.find('#meta-table').html(`
			<tr>
				<th> Partition </th>
				<th> Start </th>
				<th> End </th>
				<th> Total Messages </th>
			</tr>
		`);
		frappe.dom.freeze();
		let topic_meta, consumer_names;
		try {
			topic_meta = await frappe.xcall('latte.latte_core.page.kafka_queue_monitor.get_topic_meta', {
				topic,
				bootstrap_server,
			})
			frappe.dom.unfreeze()
		} catch (e) {
			console.log(e);
			frappe.dom.unfreeze();
			return;
		}
		this.wrapper.find('#meta-name').html(`
			Topic Meta - ${topic}
			(<a id='increase-partitions' topic="${topic}">Increase Partitions?</a>)
		`);
		this.wrapper.find('#meta-table').append(topic_meta.map(i =>
			`<tr>
				<td>${i.partition}</td>
				<td>${i.start || 0}</td>
				<td>${i.end || 0}</td>
				<td>${i.total_messages}</td>
			</tr>`
		).join('\n'));
		this.wrapper.find('#increase-partitions').click((event) => {
			const topic = event.target.attributes['topic'].value;
			frappe.prompt(`New partition count for ${topic}?`, ({value}) => {
				frappe.xcall('latte.latte_core.page.kafka_queue_monitor.create_partitions', {
					topic,
					total: value,
					bootstrap_server,
				})
			})
		})
	}

	async load_cg_meta(cg) {
		const bootstrap_server = this.page.bootstrap_server.get_value();
		this.wrapper.find('#meta-name').html(`Topic Meta - ${cg}`);
		this.wrapper.find('#meta-table').html(`
			<tr>
				<th> Topic </th>
				<th> Partition </th>
				<th> Cg Offset </th>
				<th> Offset </th>
				<th> Lag </th>
			</tr>
		`);
		frappe.dom.freeze();
		let consumer_group_meta;
		try {
			consumer_group_meta = await frappe.xcall('latte.latte_core.page.kafka_queue_monitor.get_consumer_group_meta', {
				cg,
				bootstrap_server,
			})
			frappe.dom.unfreeze()
		} catch (e) {
			console.log(e);
			frappe.dom.unfreeze();
			return;
		}
		const total_lag = consumer_group_meta.map(i => i.lag).reduce((i, j) => i + j);
		this.wrapper.find('#meta-name').html(`
			Topic Meta - ${cg} <br>
			Total Partitions - ${consumer_group_meta.length} <br>
			Total Lag: ${total_lag}
		`);
		this.wrapper.find('#meta-table').append(consumer_group_meta.map(i =>
			`<tr>
				<td>${i.topic}</td>
				<td>${i.partition}</td>
				<td>${i.cg_offset || 0}</td>
				<td>${i.offset || 0}</td>
				<td>${i.lag}</td>
			</tr>`
		).join('\n'));
	}

	async load_consumer_meta(consumer_name) {
		const bootstrap_server = this.page.bootstrap_server.get_value();
		this.wrapper.find('#meta-name').html(`Consumer Meta - ${consumer_name}`);
		this.wrapper.find('#meta-table').html(`
			<tr>
				<th> Topic </th>
				<th> Partition </th>
				<th> Cg Offset </th>
				<th> Offset </th>
				<th> Lag </th>
			</tr>
		`);

		frappe.dom.freeze();
		let consumer_meta;
		try {
			consumer_meta = await frappe.xcall('latte.latte_core.page.kafka_queue_monitor.get_consumer_meta', {
				consumer_name,
				bootstrap_server,
			})
			frappe.dom.unfreeze()
		} catch (e) {
			console.log(e);
			frappe.dom.unfreeze();
			return;
		}
		const total_lag = consumer_meta.map(i => i.lag).reduce((i, j) => i + j);
		this.wrapper.find('#meta-name').html(`
			Consumer Meta - ${consumer_name}<br>
			Total Partitions - ${consumer_meta.length} <br>
			Total Lag: ${total_lag}
		`);
		this.wrapper.find('#meta-table').append(consumer_meta.map(i =>
			`<tr>
				<td>${i.topic}</td>
				<td>${i.partition}</td>
				<td>${i.cg_offset || 0}</td>
				<td>${i.offset || 0}</td>
				<td>${i.lag}</td>
			</tr>`
		).join('\n'));
	}
}