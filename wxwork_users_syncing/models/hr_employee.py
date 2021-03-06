# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

from ...wxwork_api.CorpApi import *

from ..helper.common import *
import logging
import platform
import time

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"
    _description = "Enterprise WeChat employees"
    _order = "wxwork_user_order"

    wxwork_id = fields.Char(
        string="Enterprise WeChat user Id", readonly=True, translate=True
    )
    alias = fields.Char(string="Alias", readonly=True, translate=True)
    department_ids = fields.Many2many(
        "hr.department",
        string="Enterprise WeChat multi-department",
        readonly=True,
        translate=True,
    )
    qr_code = fields.Binary(
        string="Personal QR code",
        help="Personal QR code, Scan can be added as external contact",
        readonly=True,
        translate=True,
    )
    wxwork_user_order = fields.Char(
        "Enterprise WeChat user sort",
        default="0",
        help="The sort value within the department, the default is 0. The quantity must be the same as the department, The greater the value the more sort front.The value range is [0, 2^32)",
        readonly=True,
        translate=True,
    )
    is_wxwork_employee = fields.Boolean(
        "Enterprise WeChat employees", readonly=True, translate=True
    )

    user_check_tick = fields.Boolean(
        "User Check Tick", default=False, translate=True)

    def create_user_from_employee(self):
        """
        从员工生成用户
        :return:
        """
        groups_id = (
            self.sudo()
            .env["res.groups"]
            .search(
                [
                    ("id", "=", 9),
                ],
                limit=1,
            )
            .id
        )
        res_user_id = self.env["res.users"].create(
            {
                "name": self.name,
                "login": self.wxwork_id,
                "oauth_uid": self.wxwork_id,
                "password": Common(8).random_passwd(),
                "email": self.work_email,
                "wxwork_id": self.wxwork_id,
                "image_1920": self.image_1920,
                # 'qr_code': employee.qr_code,
                "active": self.active,
                "wxwork_user_order": self.wxwork_user_order,
                "mobile": self.mobile_phone,
                "phone": self.work_phone,
                "notification_type": "wxwork",
                "is_wxwork_user": True,
                "is_moderator": False,
                "is_company": False,
                "employee": True,
                "share": False,
                "groups_id": [(6, 0, [groups_id])],  # 设置用户为门户用户
                "tz": "Asia/Chongqing",
                "lang": "zh_CN",
            }
        )
        self.user_id = res_user_id.id
        self.address_home_id = res_user_id.partner_id.id
        self.user_check_tick = True

    @api.onchange("address_home_id")
    def user_checking(self):
        if self.address_home_id:
            self.user_check_tick = True
        else:
            self.user_check_tick = False

    def sync_employee(self):
        params = self.env["ir.config_parameter"].sudo()
        corpid = params.get_param("wxwork.corpid")
        secret = params.get_param("wxwork.contacts_secret")
        sync_department_id = params.get_param(
            "wxwork.contacts_sync_hr_department_id")
        debug = params.get_param("wxwork.debug_enabled")
        if debug:
            _logger.debug(
                _("Start syncing Enterprise WeChat Contact-Employee Synchronization")
            )
        api = CorpApi(corpid, secret)

        try:
            response = api.httpCall(
                CORP_API_TYPE["USER_LIST"],
                {
                    "department_id": sync_department_id,
                    "fetch_child": "1",
                },
            )
            start1 = time.time()
            for obj in response["userlist"]:
                self.run_sync(obj, debug)
            end1 = time.time()
            times1 = end1 - start1

            start2 = time.time()
            self.sync_leave_employee(response, debug)  # 同步离职员工
            end2 = time.time()
            times2 = end2 - start2

            times = times1 + times2
            status = {"employee": True}
            result = _("Employee synchronization succeeded, time spent %s seconds") % (
                round(times, 3)
            )
        except BaseException as e:
            times = time.time()
            result = _("Employee synchronization failed, time spent %s seconds") % (
                round(times, 3)
            )
            status = {"employee": False}

            if debug:
                print(_("Employee synchronization error:%s") % (repr(e)))

        times = times
        if debug:
            _logger.debug(_(
                "End sync Enterprise WeChat Contact - Employee Synchronization,Total time spent: %s seconds")
                % times)

        return times, status, result

    def run_sync(self, obj, debug):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            env = self.sudo().env["hr.employee"]
            domain = ["|", ("active", "=", False), ("active", "=", True)]
            records = env.search(
                domain
                + [
                    ("wxwork_id", "=", obj["userid"]),
                    ("is_wxwork_employee", "=", True),
                ],
                limit=1,
            )

            try:
                if len(records) > 0:
                    self.update_employee(records, obj, debug)
                else:
                    self.create_employee(records, obj, debug)
            except Exception as e:
                print(repr(e))
            new_cr.commit()
            new_cr.close()

    def create_employee(self, records, obj, debug):
        department_ids = []
        for department in obj["department"]:
            department_ids.append(
                self.get_employee_parent_wxwork_department(department, debug)
            )

        img_path = (
            self.env["ir.config_parameter"].sudo().get_param(
                "wxwork.contacts_img_path")
        )
        if platform.system() == "Windows":
            avatar_file = (
                img_path.replace("\\", "/") + "/avatar/" +
                obj["userid"] + ".jpg"
            )
            qr_code_file = (
                img_path.replace("\\", "/") + "/qr_code/" +
                obj["userid"] + ".png"
            )
        else:
            avatar_file = img_path + "avatar/" + obj["userid"] + ".jpg"
            qr_code_file = img_path + "qr_code/" + obj["userid"] + ".png"

        try:
            records.create(
                {
                    "wxwork_id": obj["userid"],
                    "name": obj["name"],
                    "gender": Common(obj["gender"]).gender(),
                    "marital": None,  # 不生成婚姻状况
                    "image_1920": self.encode_image_as_base64(avatar_file),
                    "mobile_phone": obj["mobile"],
                    "work_phone": obj["telephone"],
                    "work_email": obj["email"],
                    "active": obj["enable"],
                    "alias": obj["alias"],
                    # 'department_id':department_id,
                    # 归属多个部门的情况下，第一个部门为默认部门
                    "department_id": department_ids[0],
                    "department_ids": [(6, 0, department_ids)],
                    "wxwork_user_order": obj["order"],
                    "qr_code": self.encode_image_as_base64(qr_code_file),
                    "is_wxwork_employee": True,
                }
            )
            result = True
        except Exception as e:
            if debug:
                print(_("Error creating employee:%s - %s") %
                      (obj["name"], repr(e)))
            result = False
        return result

    def update_employee(self, records, obj, debug):
        params = self.env["ir.config_parameter"].sudo()
        always = params.get_param(
            "wxwork.contacts_always_update_avatar_enabled")

        department_ids = []
        for department in obj["department"]:
            department_ids.append(
                self.get_employee_parent_wxwork_department(department, debug)
            )

        img_path = (
            self.env["ir.config_parameter"].sudo().get_param(
                "wxwork.contacts_img_path")
        )
        if platform.system() == "Windows":
            avatar_file = (
                img_path.replace("\\", "/") + "/avatar/" +
                obj["userid"] + ".jpg"
            )
            qr_code_file = (
                img_path.replace("\\", "/") + "/qr_code/" +
                obj["userid"] + ".png"
            )
        else:
            avatar_file = img_path + "avatar/" + obj["userid"] + ".jpg"
            qr_code_file = img_path + "qr_code/" + obj["userid"] + ".png"
        try:
            records.write(
                {
                    "name": obj["name"],
                    "gender": Common(obj["gender"]).gender(),
                    "image_1920": self.check_always_update_avatar(always, avatar_file),
                    "mobile_phone": obj["mobile"],
                    "work_phone": obj["telephone"],
                    "work_email": obj["email"],
                    "active": obj["enable"],
                    "alias": obj["alias"],
                    # 'department_id': department_id,
                    # 归属多个部门的情况下，第一个部门为默认部门
                    "department_id": department_ids[0],
                    "department_ids": [(6, 0, department_ids)],
                    "wxwork_user_order": obj["order"],
                    "qr_code": self.encode_image_as_base64(qr_code_file),
                    "is_wxwork_employee": True,
                }
            )
            result = True
        except Exception as e:
            if debug:
                print(_("Update employee error:%s - %s") %
                      (obj["name"], repr(e)))
            result = False

        return result

    def check_always_update_avatar(self, always, avatar_file):
        if always:
            # print("一直更新图片"+avatar_file)
            return self.encode_image_as_base64(avatar_file)
        else:
            # print("不更新图片" + avatar_file)
            return None

    def encode_image_as_base64(self, image_path):
        # if not self.sync_img:
        #     return None
        if not os.path.exists(image_path):
            pass
        else:
            try:
                with open(image_path, "rb") as f:
                    encoded_string = base64.b64encode(f.read())
                return encoded_string
            except BaseException as e:
                return None
                # pass+

    def get_employee_parent_hr_department(self, department_obj):
        """
        如果企微用户只有一个部门，则设置企业用户的HR部门
        :param department_obj: 部门json
        :return:
            企微用户只有一个部门，返回department_id
            企微用户归属多个部门，返回 None
        """
        try:
            departments = self.env["hr.department"].search(
                [
                    ("wxwork_department_id", "in", department_obj),
                    ("is_wxwork_department", "=", True),
                ],
                limit=1,
            )
            if len(departments) > 0:
                return departments.id
        except BaseException as e:
            pass
            # print("获取员工上级部门错误:%s" % (repr(e)))

    def get_employee_parent_wxwork_department(self, department_id, debug):
        try:
            departments = self.env["hr.department"].search(
                [
                    ("wxwork_department_id", "=", department_id),
                    ("is_wxwork_department", "=", True),
                ],
                limit=1,
            )
            if len(departments) > 0:
                return departments.id
        except BaseException as e:
            if debug:
                print(_("Get the employee's parent department error:%s") %
                      (repr(e)))

    def sync_leave_employee(self, response, debug):
        """比较企业微信和odoo的员工数据，且设置离职odoo员工active状态"""
        try:
            list_user = []
            list_employee = []
            for wxwork_employee in response["userlist"]:
                list_user.append(wxwork_employee["userid"])

            with api.Environment.manage():
                new_cr = self.pool.cursor()
                self = self.with_env(self.env(cr=new_cr))
                env = self.sudo().env["hr.employee"]
                domain = ["|", ("active", "=", False), ("active", "=", True)]
                employees = env.search(
                    domain + [("is_wxwork_employee", "=", True)])
                for employee in employees:
                    list_employee.append(employee.wxwork_id)

                list_user_leave = list(
                    set(list_employee).difference(set(list_user))
                )  # 生成odoo与企微不同的员工数据列表
                for wxwork_leave_employee in list_user_leave:
                    leave_employee = employees.search(
                        [("wxwork_id", "=", wxwork_leave_employee)]
                    )
                    self.set_employee_active(leave_employee, debug)
                    # print(leave_employee.name + str(op))
                new_cr.commit()
                new_cr.close()
        except Exception as e:
            if debug:
                print(
                    _("Errors in generating data for departing employees:%s")
                    % (repr(e))
                )

    def set_employee_active(self, records, debug):
        try:
            records.write(
                {
                    "active": False,
                }
            )
            # return True
        except Exception as e:
            if debug:
                print(
                    _("Departed employee: %s Synchronization error: %s")
                    % (records.name, repr(e))
                )


class EmployeeSyncUser(models.Model):
    _inherit = "hr.employee"
    _description = "Enterprise WeChat employees bind system users"

    def sync_user(self):
        params = self.env["ir.config_parameter"].sudo()
        debug = params.get_param("wxwork.debug_enabled")

        if debug:
            _logger.info(_("Start syncing from employees to system users"))

        domain = ["|", ("active", "=", False), ("active", "=", True)]

        try:
            with api.Environment.manage():
                new_cr = self.pool.cursor()
                self = self.with_env(self.env(cr=new_cr))

                employees = (
                    self.sudo()
                    .env["hr.employee"]
                    .search(
                        domain
                        + [
                            ("is_wxwork_employee", "=", True),
                            ("user_check_tick", "=", False),
                        ]
                    )
                )
                start = time.time()
                result = _(
                    "There is currently no employee profile that needs to generate system users"
                )
                status = False
                for employee in employees:
                    user = (
                        self.sudo()
                        .env["res.users"]
                        .search(
                            domain
                            + [
                                ("wxwork_id", "=", employee.wxwork_id),
                                ("is_wxwork_user", "=", True),
                            ],
                            limit=1,
                        )
                    )

                    try:
                        if len(user) > 0:
                            self.update_user(user, employee, debug)
                        else:
                            self.create_user(user, employee, debug)

                        result = _(
                            "Employee synchronization is successful as system user"
                        )
                        status = True
                    except Exception as e:
                        result = "员工同步用户失败"
                        status = False
                        print(
                            _("Failed to synchronize employee as system user:%s")
                            % (repr(e))
                        )

                end = time.time()
                times = end - start

                new_cr.commit()
                new_cr.close()

                if debug:
                    _logger.info(
                        _(
                            "Finished synchronizing enterprise WeChat contacts - employee synchronization system users, total time spent: %s seconds"
                        )
                        % times
                    )
        except BaseException as e:
            if debug:
                _logger.warning(
                    _("Employee synchronization as system user error: %s seconds")
                    % (repr(e))
                )
            result = _("Failed to synchronize employee as system user")
            status = False

        return times, status, result

    def create_user(self, user, employee, debug):
        try:
            groups_id = (
                self.sudo()
                .env["res.groups"]
                .search(
                    [
                        ("id", "=", 9),
                    ],
                    limit=1,
                )
                .id
            )
            user = user.create(
                {
                    "name": employee.name,
                    "login": employee.wxwork_id,
                    "oauth_uid": employee.wxwork_id,
                    "password": Common(8).random_passwd(),  # 随机密码
                    "email": employee.work_email,
                    "wxwork_id": employee.wxwork_id,
                    "image_1920": employee.image_1920,
                    # 'qr_code': employee.qr_code,
                    "active": employee.active,
                    "wxwork_user_order": employee.wxwork_user_order,
                    "mobile": employee.mobile_phone,
                    "phone": employee.work_phone,
                    "notification_type": "wxwork",
                    "is_wxwork_user": True,
                    "is_moderator": False,
                    "is_company": False,
                    "employee": True,
                    "share": False,
                    "groups_id": [(6, 0, [groups_id])],  # 设置用户为门户用户
                    "tz": "Asia/Chongqing",
                    "lang": "zh_CN",
                }
            )

            employee.write(
                {
                    "user_id": user.id,
                    "address_home_id": user.partner_id.id,
                    "user_check_tick": True,
                }
            )
        except Exception as e:
            if debug:
                print(_("Error creating system user from employee:%s") % (repr(e)))

    def update_user(self, user, employee, debug):
        try:
            user.write(
                {
                    "name": employee.name,
                    "oauth_uid": employee.wxwork_id,
                    # 'email': employee.work_email,
                    "image_1920": employee.image_1920,
                    "wxwork_user_order": employee.wxwork_user_order,
                    "is_wxwork_user": True,
                    "mobile": employee.mobile_phone,
                    "phone": employee.work_phone,
                }
            )
        except Exception as e:
            if debug:
                print(_("Error creating system user from employee:%s") % (repr(e)))
