// frappe.ui.form.on('Employee Checkin', {
//     refresh: function (frm) {
//         // Add a custom button to calculate deduction
//         frm.add_custom_button(__('Calculate Deduction'), function () {
//             calculateDeduction(frm);
//         });
//     },
//     time: function (frm) {
//         calculateDeduction(frm);
//     }
// });

// function calculateDeduction(frm) {
//     if (!frm.doc.time || !frm.doc.employee) {
//         return;
//     }

//     frappe.call({
//         method: 'frappe.client.get_value',
//         args: {
//             doctype: 'Employee',
//             filters: { name: frm.doc.employee },
//             fieldname: ['default_shift', 'employee_name']
//         },
//         callback: function (response) {
//             if (response.message && response.message.default_shift) {
//                 const shiftType = response.message.default_shift;

//                 frappe.call({
//                     method: 'frappe.client.get_value',
//                     args: {
//                         doctype: 'Shift Type',
//                         filters: { name: shiftType },
//                         fieldname: ['start_time', 'name']
//                     },
//                     callback: function (r) {
//                         if (r.message && r.message.start_time) {
//                             const shiftStartTime = r.message.start_time;
//                             const checkinTime = frm.doc.time;

//                             // Get hours and minutes separately for both times
//                             const checkinHours = moment(checkinTime).hours();
//                             const checkinMinutes = moment(checkinTime).minutes();
//                             const [shiftHours, shiftMinutes] = shiftStartTime.split(':').map(Number);

//                             // Calculate total minutes for each time
//                             const checkinTotalMinutes = (checkinHours * 60) + checkinMinutes;
//                             const shiftTotalMinutes = (shiftHours * 60) + shiftMinutes;

//                             // Calculate the difference
//                             let diffInMinutes = checkinTotalMinutes - shiftTotalMinutes;

//                             console.log('=== Detailed Calculation ===');
//                             console.log('Check-in time:', checkinHours + ':' + checkinMinutes);
//                             console.log('Shift start time:', shiftHours + ':' + shiftMinutes);
//                             console.log('Check-in total minutes:', checkinTotalMinutes);
//                             console.log('Shift total minutes:', shiftTotalMinutes);
//                             console.log('Difference in minutes:', diffInMinutes);
//                             console.log('Difference in hours (should be):', diffInMinutes / 60);
//                             console.log('Current wrong hours value:', 0.2500);
//                             console.log('Correct hours value should be:', (diffInMinutes / 60).toFixed(4));

//                             // Only consider late arrivals (positive values)
//                             diffInMinutes = Math.max(0, diffInMinutes);

//                             // Convert to hours correctly
//                             const hoursLate = diffInMinutes;

//                             // Set the value
//                             frm.set_value('custom_deduction', hoursLate);
//                             frm.save();
//                         }
//                     }
//                 });
//             }
//         }
//     });
// }