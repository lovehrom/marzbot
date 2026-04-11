from typing import Any, Dict, List, Type, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="UserCreateInbounds")


@_attrs_define
class UserCreateInbounds:
    """ """

    additional_properties: Dict[str, List[str]] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        field_dict: Dict[str, Any] = {}
        for prop_name, prop in self.additional_properties.items():
            field_dict[prop_name] = prop

        field_dict.update({})

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Any) -> T:
        # ПРОВЕРКА: если данных нет
        if src_dict is None:
            return cls()

        # ПРОВЕРКА: если пришел список (например, ["vless"])
        if isinstance(src_dict, list):
            d = {item: [] for item in src_dict}
        # ПРОВЕРКА: если пришел словарь
        elif isinstance(src_dict, dict):
            d = src_dict.copy()
        else:
            d = {}

        user_create_inbounds = cls()
        additional_properties = {}

        for prop_name, prop_dict in d.items():
            # Защита: если внутри элемента списка не список строк
            if isinstance(prop_dict, list):
                additional_property = cast(List[str], prop_dict)
            else:
                additional_property = []

            additional_properties[prop_name] = additional_property

        user_create_inbounds.additional_properties = additional_properties
        return user_create_inbounds

    @property
    def additional_keys(self) -> List[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> List[str]:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: List[str]) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
